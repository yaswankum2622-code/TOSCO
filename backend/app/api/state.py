"""In-memory API state for orchestrated TOSCO demo runs."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

from app.engine.ledger import HashLedger, LedgerEntry, LedgerError
from app.orchestrator.runner import OrchestratedRun, OrchestratorConfig, OrchestratorError, run_scenario
from app.scenarios.loader import SCENARIOS, ScenarioLoadError, load_scenario_seed


def _require_non_empty(value: str, field_name: str) -> str:
    """Reject blank API-state identifiers."""

    trimmed = value.strip()
    if not trimmed:
        raise ValueError(f"{field_name} cannot be empty")
    return trimmed


class ApiStateError(RuntimeError):
    """Signal user-facing API state failures with safe status metadata."""

    def __init__(self, detail: str, *, error: str, status_code: int) -> None:
        super().__init__(detail)
        self.detail = detail
        self.error = error
        self.status_code = status_code


class ApiRunRecord(BaseModel):
    """Persist one orchestrated run plus its demo tamper state."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    scenario: str
    orchestrated_run: OrchestratedRun
    tampered: bool = False
    tamper_reason: str | None = None

    @field_validator("run_id", "scenario")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank run metadata."""

        return _require_non_empty(value, info.field_name)


class InMemoryApiState:
    """Keep one shared ledger and insertion-ordered demo runs in memory."""

    def __init__(self) -> None:
        self.ledger = HashLedger()
        self.runs: dict[str, ApiRunRecord] = {}

    def start_run(
        self,
        scenario: str,
        config: OrchestratorConfig | None = None,
    ) -> ApiRunRecord:
        """Start one orchestrated run and store it by deterministic run_id."""

        normalized_scenario = _require_non_empty(scenario, "scenario").lower()
        if normalized_scenario not in SCENARIOS:
            allowed = ", ".join(sorted(SCENARIOS))
            raise ApiStateError(
                f"Invalid scenario '{scenario}'. Allowed scenarios: {allowed}",
                error="INVALID_SCENARIO",
                status_code=400,
            )

        try:
            seed = load_scenario_seed(normalized_scenario)
        except ScenarioLoadError as exc:
            raise ApiStateError(
                "Scenario metadata could not be loaded.",
                error="SCENARIO_LOAD_FAILED",
                status_code=500,
            ) from exc

        if seed.run_id in self.runs:
            raise ApiStateError(
                f"Run '{seed.run_id}' already exists. Reset demo state before rerunning this scenario.",
                error="RUN_ALREADY_EXISTS",
                status_code=400,
            )

        try:
            orchestrated_run = run_scenario(normalized_scenario, config=config, ledger=self.ledger)
        except OrchestratorError as exc:
            raise ApiStateError(
                "The backend could not start the requested run.",
                error="RUN_START_FAILED",
                status_code=500,
            ) from exc

        record = ApiRunRecord(
            run_id=orchestrated_run.run_context.run_id,
            scenario=orchestrated_run.scenario,
            orchestrated_run=orchestrated_run,
        )
        self.runs[record.run_id] = record
        return record

    def get_run(self, run_id: str) -> ApiRunRecord:
        """Return one stored run by ID."""

        normalized_run_id = _require_non_empty(run_id, "run_id")
        try:
            return self.runs[normalized_run_id]
        except KeyError as exc:
            raise ApiStateError(
                f"Run '{normalized_run_id}' was not found.",
                error="RUN_NOT_FOUND",
                status_code=404,
            ) from exc

    def list_runs(self) -> list[ApiRunRecord]:
        """Return stored runs in insertion order."""

        return list(self.runs.values())

    def reset(self) -> None:
        """Clear demo runs and start a fresh shared ledger."""

        self.runs = {}
        self.ledger = HashLedger()

    def verify_run(self, run_id: str) -> dict[str, Any]:
        """Verify one run's packet against the shared ledger state."""

        record = self.get_run(run_id)
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
            "verified": ledger_chain_valid and packet_entry_valid and proof_hash_matches,
        }

    def tamper_run(self, run_id: str) -> dict[str, Any]:
        """Mutate one ledger entry for demo purposes and return the new verification result."""

        record = self.get_run(run_id)
        try:
            self.ledger.tamper_entry_for_demo(
                record.orchestrated_run.ledger_entry.index,
                packet_hash="f" * 64,
            )
        except LedgerError as exc:
            raise ApiStateError(
                "The demo ledger could not be tampered.",
                error="TAMPER_FAILED",
                status_code=500,
            ) from exc

        self.runs[record.run_id] = record.model_copy(
            update={
                "tampered": True,
                "tamper_reason": "Ledger packet hash replaced for demo tamper.",
            }
        )
        return self.verify_run(run_id)

    def _current_ledger_entry(self, record: ApiRunRecord) -> LedgerEntry:
        """Resolve the current shared-ledger entry for a stored run."""

        index = record.orchestrated_run.ledger_entry.index
        try:
            entry = self.ledger.entries[index]
        except IndexError as exc:
            raise ApiStateError(
                "The ledger entry for this run is missing.",
                error="LEDGER_ENTRY_MISSING",
                status_code=500,
            ) from exc

        if entry.run_id != record.run_id:
            raise ApiStateError(
                "The ledger entry for this run is inconsistent.",
                error="LEDGER_ENTRY_MISMATCH",
                status_code=500,
            )

        return entry
