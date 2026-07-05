"""In-memory API state and SSE orchestration support for TOSCO demo runs."""

from __future__ import annotations

import asyncio
import threading
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

from app.api.sse_bus import ContractEventMessage, RunSseBus
from app.engine.ledger import HashLedger, LedgerEntry, LedgerError
from app.custom.builder import CustomRunInput, build_custom_proposal, build_custom_seed
from app.orchestrator.runner import (
    OrchestratedRun,
    OrchestratorConfig,
    OrchestratorError,
    run_from_seed,
)
from app.scenarios.loader import SCENARIOS, ScenarioLoadError, ScenarioSeed, load_scenario_seed
from app.agent.reference_ap_agent import ReferenceAPAgent, AgentProposal
from app.models import ActionIntent


def _require_non_empty(value: str, field_name: str) -> str:
    """Reject blank API-state identifiers."""

    trimmed = value.strip()
    if not trimmed:
        raise ValueError(f"{field_name} cannot be empty")
    return trimmed


class ApiStateError(RuntimeError):
    """Signal user-facing API state failures with safe status metadata."""

    def __init__(self, message: str, *, error_code: str, status_code: int) -> None:
        super().__init__(message)
        self.message = message
        self.detail = message
        self.error_code = error_code
        self.error = error_code
        self.status_code = status_code


@dataclass(slots=True)
class ApiRunRecord:
    """Hold all mutable runtime state for one orchestrated run."""

    run_id: str
    scenario: str
    workflow_id: str
    intent: ActionIntent
    evidence_refs: list[str]
    bus: RunSseBus
    loop: asyncio.AbstractEventLoop
    status: str = "PENDING"
    orchestrated_run: OrchestratedRun | None = None
    extraction_hash: str | None = None
    fallback_mode: bool = False
    decision: str | None = None
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    gate_results: list[dict[str, Any]] = field(default_factory=list)
    clearance_token: str | None = None
    error_message: str | None = None
    completed_event: asyncio.Event = field(default_factory=asyncio.Event)

    def to_snapshot(self) -> dict[str, Any]:
        """Return the contract snapshot payload for this run."""

        return {
            "run_id": self.run_id,
            "workflow_id": self.workflow_id,
            "status": self.status,
            "intent": None if self.intent is None else self.intent.model_dump(mode="json"),
            "evidence_refs": list(self.evidence_refs),
            "extraction_hash": self.extraction_hash,
            "tool_calls": list(self.tool_calls),
            "gate_results": list(self.gate_results),
            "decision": self.decision,
            "fallback_mode": self.fallback_mode,
            "clearance_token": self.clearance_token,
            "error_message": self.error_message,
        }


class InMemoryApiState:
    """Keep one shared ledger, proposal state, and per-run SSE buses in memory."""

    def __init__(self) -> None:
        self.ledger = HashLedger()
        self.runs: dict[str, ApiRunRecord] = {}
        self.proposals: dict[str, ActionIntent] = {}
        self._tasks: set[asyncio.Task[None]] = set()
        self._lock = threading.Lock()
        self._ledger_lock = threading.Lock()

    def register_proposal(self, intent: ActionIntent) -> None:
        """Persist a proposal intent so the public control plane can inspect it later."""

        self.proposals[intent.intent_id] = intent

    async def start_run(
        self,
        scenario: str,
        config: OrchestratorConfig | None = None,
        *,
        use_vultr: bool = False,
    ) -> ApiRunRecord:
        """Start one orchestrated run in the background and return its handle immediately."""

        normalized_scenario = _require_non_empty(scenario, "scenario").lower()
        if normalized_scenario not in SCENARIOS:
            allowed = ", ".join(sorted(SCENARIOS))
            raise ApiStateError(
                f"Invalid scenario '{scenario}'. Allowed scenarios: {allowed}",
                error_code="INVALID_SCENARIO",
                status_code=400,
            )

        try:
            seed = load_scenario_seed(normalized_scenario)
        except ScenarioLoadError as exc:
            raise ApiStateError(
                "Scenario metadata could not be loaded.",
                error_code="SCENARIO_LOAD_FAILED",
                status_code=500,
            ) from exc

        with self._lock:
            if seed.run_id in self.runs:
                raise ApiStateError(
                    f"Run '{seed.run_id}' already exists. Reset demo state before rerunning this scenario.",
                    error_code="RUN_ALREADY_EXISTS",
                    status_code=400,
                )

            proposal = ReferenceAPAgent().propose_from_seed(seed)
            self.proposals[proposal.intent.intent_id] = proposal.intent
            loop = asyncio.get_running_loop()
            record = ApiRunRecord(
                run_id=seed.run_id,
                scenario=normalized_scenario,
                workflow_id=seed.workflow_id,
                intent=proposal.intent,
                evidence_refs=list(proposal.intent.evidence_refs),
                bus=RunSseBus(seed.run_id, loop),
                loop=loop,
            )
            self.runs[record.run_id] = record

        active_config = (
            OrchestratorConfig(use_vultr=use_vultr)
            if config is None
            else config.model_copy(update={"use_vultr": use_vultr})
        )
        task = asyncio.create_task(self._execute_run(record.run_id, seed, active_config))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return record

    async def start_custom_run(
        self,
        payload: CustomRunInput,
        config: OrchestratorConfig | None = None,
    ) -> ApiRunRecord:
        """Start one judge-supplied custom run through the full clearance pipeline."""

        seed = build_custom_seed(payload)
        proposal = build_custom_proposal(seed)

        with self._lock:
            loop = asyncio.get_running_loop()
            record = ApiRunRecord(
                run_id=seed.run_id,
                scenario="custom",
                workflow_id=seed.workflow_id,
                intent=proposal.intent,
                evidence_refs=list(proposal.intent.evidence_refs),
                bus=RunSseBus(seed.run_id, loop),
                loop=loop,
            )
            self.runs[record.run_id] = record
            self.proposals[proposal.intent.intent_id] = proposal.intent

        active_config = (
            OrchestratorConfig(use_vultr=payload.use_vultr)
            if config is None
            else config.model_copy(update={"use_vultr": payload.use_vultr})
        )
        task = asyncio.create_task(
            self._execute_run(record.run_id, seed, active_config, proposal=proposal)
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return record

    async def _execute_run(
        self,
        run_id: str,
        seed: ScenarioSeed,
        config: OrchestratorConfig,
        *,
        proposal: AgentProposal | None = None,
    ) -> None:
        """Run the existing orchestrator in a worker thread and persist its final state."""

        record = self.get_run(run_id)

        def contract_emit(event_name: str, data: dict[str, Any] | None) -> None:
            record.bus.publish(event_name, data)

        try:
            with self._ledger_lock:
                orchestrated_run = await asyncio.to_thread(
                    run_from_seed,
                    seed,
                    config=config,
                    ledger=self.ledger,
                    contract_event_emitter=contract_emit,
                    proposal=proposal,
                )
        except OrchestratorError as exc:
            record.status = "FAILED"
            record.error_message = str(exc)
            record.bus.complete()
            record.loop.call_soon_threadsafe(record.completed_event.set)
            return
        except Exception as exc:  # pragma: no cover - defensive runtime guard
            record.status = "FAILED"
            record.error_message = "The backend run failed unexpectedly."
            record.bus.complete()
            record.loop.call_soon_threadsafe(record.completed_event.set)
            raise exc

        record.orchestrated_run = orchestrated_run
        record.status = "COMPLETED"
        record.extraction_hash = (
            orchestrated_run.run_context.extraction.sealed_hash()
            if orchestrated_run.run_context.extraction is not None
            else None
        )
        record.fallback_mode = orchestrated_run.run_context.fallback_mode
        record.decision = orchestrated_run.final_decision.value
        record.tool_calls = [
            tool_call.model_dump(mode="json")
            for tool_call in orchestrated_run.run_context.tool_calls
        ]
        record.gate_results = [
            gate_result.model_dump(mode="json")
            for gate_result in orchestrated_run.outcome.gate_results
        ]
        record.clearance_token = (
            orchestrated_run.clearance_token.model_dump_json()
            if orchestrated_run.clearance_token is not None
            else None
        )
        record.bus.complete()
        record.loop.call_soon_threadsafe(record.completed_event.set)

    def get_run(self, run_id: str) -> ApiRunRecord:
        """Return one stored run by ID."""

        normalized_run_id = _require_non_empty(run_id, "run_id")
        try:
            return self.runs[normalized_run_id]
        except KeyError as exc:
            raise ApiStateError(
                f"Run '{normalized_run_id}' was not found.",
                error_code="RUN_NOT_FOUND",
                status_code=404,
            ) from exc

    async def wait_for_completion(
        self,
        run_id: str,
        *,
        timeout_seconds: float = 10.0,
    ) -> ApiRunRecord:
        """Wait briefly for one run to complete so legacy routes remain usable."""

        record = self.get_run(run_id)
        if record.status in {"COMPLETED", "FAILED"}:
            return record

        try:
            await asyncio.wait_for(record.completed_event.wait(), timeout=timeout_seconds)
        except TimeoutError as exc:
            raise ApiStateError(
                f"Run '{run_id}' is still processing.",
                error_code="RUN_NOT_READY",
                status_code=409,
            ) from exc

        return record

    async def subscribe_contract_events(
        self,
        run_id: str,
    ) -> AsyncIterator[ContractEventMessage]:
        """Yield the contract event backlog and any future events for one run."""

        record = self.get_run(run_id)
        async for message in record.bus.subscribe():
            yield message

    def list_runs(self) -> list[ApiRunRecord]:
        """Return stored runs in insertion order."""

        return list(self.runs.values())

    def latest_run(self) -> ApiRunRecord | None:
        """Return the most recently created run record, if any."""

        if not self.runs:
            return None
        return next(reversed(self.runs.values()))

    def reset(self) -> None:
        """Clear demo runs, proposals, and the shared ledger."""

        self.proposals = {}
        self.runs = {}
        self.ledger = HashLedger()

    def build_run_snapshot(self, run_id: str) -> dict[str, Any]:
        """Build the public poll-fallback snapshot for one run."""

        record = self.get_run(run_id)
        return record.to_snapshot()

    def verify_run(self, run_id: str) -> dict[str, Any]:
        """Verify one run's packet against the shared ledger state."""

        record = self.get_run(run_id)
        if record.orchestrated_run is None:
            raise ApiStateError(
                f"Run '{run_id}' has not sealed proof yet.",
                error_code="PROOF_NOT_READY",
                status_code=409,
            )

        current_entry = self._current_ledger_entry(record)
        proof_packet = record.orchestrated_run.proof_packet
        proof_hash = proof_packet.proof_hash()
        ledger_chain_valid = self.ledger.verify_chain()
        packet_entry_valid = self.ledger.verify_packet_entry(proof_packet, current_entry)
        proof_hash_matches = proof_hash == current_entry.packet_hash

        return {
            "run_id": record.run_id,
            "ledger_chain_valid": ledger_chain_valid,
            "packet_entry_valid": packet_entry_valid,
            "proof_hash": proof_hash,
            "ledger_entry_hash": current_entry.entry_hash,
            "chain_head": current_entry.entry_hash,
            "verified": ledger_chain_valid and packet_entry_valid and proof_hash_matches,
        }

    def tamper_run(self, run_id: str) -> dict[str, Any]:
        """Mutate one ledger entry for demo purposes and return the new verification result."""

        record = self.get_run(run_id)
        if record.orchestrated_run is None:
            raise ApiStateError(
                f"Run '{run_id}' has not sealed proof yet.",
                error_code="PROOF_NOT_READY",
                status_code=409,
            )

        try:
            self.ledger.tamper_entry_for_demo(
                record.orchestrated_run.ledger_entry.index,
                packet_hash="f" * 64,
            )
        except LedgerError as exc:
            raise ApiStateError(
                "The demo ledger could not be tampered.",
                error_code="TAMPER_FAILED",
                status_code=500,
            ) from exc

        verification = self.verify_run(run_id)
        verification["tampered_field"] = "packet_hash"
        verification["verify_now"] = verification["verified"]
        return verification

    def _current_ledger_entry(self, record: ApiRunRecord) -> LedgerEntry:
        """Resolve the current shared-ledger entry for a stored run."""

        if record.orchestrated_run is None:
            raise ApiStateError(
                f"Run '{record.run_id}' has not sealed proof yet.",
                error_code="PROOF_NOT_READY",
                status_code=409,
            )

        index = record.orchestrated_run.ledger_entry.index
        try:
            entry = self.ledger.entries[index]
        except IndexError as exc:
            raise ApiStateError(
                "The ledger entry for this run is missing.",
                error_code="LEDGER_ENTRY_MISSING",
                status_code=500,
            ) from exc

        if entry.run_id != record.run_id:
            raise ApiStateError(
                "The ledger entry for this run is inconsistent.",
                error_code="LEDGER_ENTRY_MISMATCH",
                status_code=500,
            )

        return entry
