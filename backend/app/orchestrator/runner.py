"""Run deterministic in-memory TOSCO demo scenarios end to end."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationInfo, computed_field, field_validator

from app.agent.reference_ap_agent import AgentProposal, ReferenceAPAgent, build_run_context_from_agent_proposal
from app.engine.ledger import HashLedger, LedgerEntry
from app.engine.mock_bank import (
    MockBankExecutionResult,
    PaymentExecutionRequest,
    attempt_mock_bank_execution,
    build_payment_request_from_context,
)
from app.engine.pipeline import ClearanceOutcome, run_clearance
from app.engine.proof import ProofPacket, create_proof_packet
from app.engine.token import ClearanceToken, TokenError, issue_clearance_token
from app.engine.workflow import load_workflow_definition
from app.models import Decision, RunContext, WorkflowDefinition
from app.orchestrator.events import EventType, EventTimeline, TimelineBuilder
from app.scenarios.loader import ScenarioLoadError, ScenarioSeed, load_scenario_seed


def _require_non_empty(value: str, field_name: str) -> str:
    """Reject blank orchestrator config fields."""

    trimmed = value.strip()
    if not trimmed:
        raise ValueError(f"{field_name} cannot be empty")
    return trimmed


class OrchestratorError(RuntimeError):
    """Signal invalid scenario orchestration state or failures."""


class OrchestratorConfig(BaseModel):
    """Hold deterministic settings for one orchestrated demo run."""

    model_config = ConfigDict(extra="forbid")

    workflow_path: str = "backend/workflows/vendor_payment.yaml"
    token_secret: str = "local-demo-secret"
    issued_at: str = "2026-07-04T12:00:00Z"
    expires_at: str = "2026-07-04T12:10:00Z"
    now: str = "2026-07-04T12:05:00Z"

    @field_validator("workflow_path", "token_secret", "issued_at", "expires_at", "now")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank orchestrator config values."""

        return _require_non_empty(value, info.field_name)


class OrchestratedRun(BaseModel):
    """Capture every major artifact produced by an orchestrated scenario run."""

    model_config = ConfigDict(extra="forbid")

    scenario: str
    seed: ScenarioSeed
    proposal: AgentProposal
    run_context: RunContext
    outcome: ClearanceOutcome
    proof_packet: ProofPacket
    ledger_entry: LedgerEntry
    clearance_token: ClearanceToken | None = None
    payment_request: PaymentExecutionRequest
    execution_result: MockBankExecutionResult
    timeline: EventTimeline

    @computed_field
    @property
    def final_decision(self) -> Decision:
        """Expose the final decision directly for convenience."""

        return self.outcome.final_decision

    @computed_field
    @property
    def allow_execution(self) -> bool:
        """Expose the execution eligibility directly for convenience."""

        return self.outcome.allow_execution


def _resolve_workflow_path(path_value: str) -> Path:
    """Resolve workflow paths robustly from tests or project-root execution."""

    raw_path = Path(path_value)
    if raw_path.is_absolute() and raw_path.exists():
        return raw_path
    if raw_path.exists():
        return raw_path.resolve()

    project_root = Path(__file__).resolve().parents[3]
    candidate = project_root / raw_path
    if candidate.exists():
        return candidate

    backend_root = Path(__file__).resolve().parents[2]
    fallback = backend_root / raw_path.name
    if fallback.exists():
        return fallback

    raise OrchestratorError(f"Workflow path not found: {path_value}")


def _tool_event_payload(workflow: WorkflowDefinition, run_context: RunContext, tool_id: str) -> dict[str, Any]:
    """Build deterministic simulated tool payloads for the event timeline."""

    del workflow
    return {
        "tool_id": tool_id,
        "simulated": True,
        "signal_keys": sorted(run_context.signals.keys()),
    }


def run_scenario(
    scenario: str,
    *,
    config: OrchestratorConfig | None = None,
    ledger: HashLedger | None = None,
) -> OrchestratedRun:
    """Run one demo scenario through proposal, clearance, proof, token, and execution."""

    active_config = config or OrchestratorConfig()
    active_ledger = ledger or HashLedger()

    try:
        workflow = load_workflow_definition(_resolve_workflow_path(active_config.workflow_path))
        seed = load_scenario_seed(scenario)
    except ScenarioLoadError as exc:
        raise OrchestratorError(f"Scenario loading failed: {exc}") from exc
    except Exception as exc:
        raise OrchestratorError(f"Workflow loading failed: {exc}") from exc

    if seed.workflow_id != workflow.workflow_id:
        raise OrchestratorError(
            f"Scenario workflow_id '{seed.workflow_id}' does not match loaded workflow '{workflow.workflow_id}'"
        )

    agent = ReferenceAPAgent()
    proposal = agent.propose_from_seed(seed)
    run_context = build_run_context_from_agent_proposal(seed, proposal)
    if run_context.workflow_id != workflow.workflow_id:
        raise OrchestratorError(
            f"RunContext workflow_id '{run_context.workflow_id}' does not match workflow '{workflow.workflow_id}'"
        )

    timeline_builder = TimelineBuilder(run_context.run_id)
    timeline_builder.add(
        EventType.AGENT_PROPOSED.value,
        "Agent Proposed Payment",
        "The reference AP agent proposed a payment action from seeded documents.",
        {
            "scenario": seed.scenario,
            "naive_action": proposal.naive_action,
            "vendor_id": proposal.intent.action.vendor_id,
            "amount": proposal.intent.action.amount,
            "bank_account_last4": proposal.intent.action.bank_account_last4,
        },
    )
    timeline_builder.add(
        EventType.PLAN_STARTED.value,
        "Clearance Plan Started",
        "TOSCO loaded the workflow definition and planned the deterministic clearance path.",
        {
            "workflow_id": workflow.workflow_id,
            "workflow_name": workflow.workflow_name,
            "gates_to_run": list(workflow.gates_to_run),
        },
    )
    timeline_builder.add(
        EventType.EVIDENCE_RETRIEVED.value,
        "Evidence Retrieved",
        "Seeded evidence was loaded for the clearance run.",
        {
            "evidence_types": sorted(run_context.evidence.keys()),
            "evidence_count": len(run_context.evidence),
        },
    )
    timeline_builder.add(
        EventType.EXTRACTION_STARTED.value,
        "Extraction Review Started",
        "The orchestrator prepared the sealed extraction for deterministic review.",
        {"extractor": run_context.extraction.extractor if run_context.extraction else "none"},
    )
    timeline_builder.add(
        EventType.EXTRACTION_SEALED.value,
        "Extraction Sealed",
        "The extraction boundary was sealed before gates evaluated typed facts.",
        {
            "extraction_hash": run_context.extraction.sealed_hash() if run_context.extraction else None,
            "required_fields": list(workflow.extraction_schema.get("required_fields", [])),
        },
    )

    for tool_id in workflow.tools_to_call:
        timeline_builder.add(
            EventType.TOOL_CALLED.value,
            "Simulated Tool Call",
            f"The orchestrator recorded a simulated call for {tool_id}.",
            _tool_event_payload(workflow, run_context, tool_id),
        )

    outcome = run_clearance(run_context, workflow)

    for gate_result in outcome.gate_results:
        timeline_builder.add(
            EventType.GATE_STARTED.value,
            "Gate Started",
            f"{gate_result.gate_id} began deterministic evaluation.",
            {"gate_id": gate_result.gate_id},
        )
        timeline_builder.add(
            EventType.GATE_COMPLETED.value,
            "Gate Completed",
            f"{gate_result.gate_id} completed deterministic evaluation.",
            {
                "gate_id": gate_result.gate_id,
                "status": gate_result.status.value,
                "decision": gate_result.decision.value,
                "reason_code": gate_result.reason_code,
            },
        )

    timeline_builder.add(
        EventType.DECISION_MADE.value,
        "Decision Made",
        "The deterministic decision engine folded all gate results into a final verdict.",
        {
            "final_decision": outcome.final_decision.value,
            "status": outcome.decision_summary.status,
            "allow_execution": outcome.allow_execution,
            "reason_codes": list(outcome.decision_summary.reason_codes),
        },
    )

    proof_packet = create_proof_packet(run_context, outcome)
    timeline_builder.add(
        EventType.PROOF_SEALED.value,
        "Proof Packet Sealed",
        "A deterministic proof packet was created for the clearance decision.",
        {
            "proof_hash": proof_packet.proof_hash(),
            "final_decision": proof_packet.final_decision.value,
        },
    )

    ledger_entry = active_ledger.append(proof_packet)
    timeline_builder.add(
        EventType.LEDGER_APPENDED.value,
        "Ledger Appended",
        "The proof packet hash was appended to the in-memory SHA-256 ledger.",
        {
            "ledger_index": ledger_entry.index,
            "ledger_entry_hash": ledger_entry.entry_hash,
            "previous_hash": ledger_entry.previous_hash,
        },
    )

    clearance_token: ClearanceToken | None = None
    if outcome.allow_execution:
        try:
            clearance_token = issue_clearance_token(
                ctx=run_context,
                outcome=outcome,
                packet=proof_packet,
                ledger_entry=ledger_entry,
                secret=active_config.token_secret,
                issued_at=active_config.issued_at,
                expires_at=active_config.expires_at,
            )
        except TokenError as exc:
            raise OrchestratorError(f"Token issuance failed: {exc}") from exc

        timeline_builder.add(
            EventType.CLEARANCE_TOKEN_ISSUED.value,
            "Clearance Token Issued",
            "A clearance token was issued because the run was allowed to execute.",
            {
                "token_id": clearance_token.token_id,
                "expires_at": clearance_token.expires_at,
            },
        )
    else:
        timeline_builder.add(
            EventType.CLEARANCE_TOKEN_SKIPPED.value,
            "Clearance Token Skipped",
            "No clearance token was issued because only ALLOW outcomes can execute.",
            {
                "final_decision": outcome.final_decision.value,
                "reason": "Token is issued only for ALLOW outcomes.",
            },
        )

    payment_request = build_payment_request_from_context(run_context, clearance_token)
    timeline_builder.add(
        EventType.EXECUTION_ATTEMPTED.value,
        "Execution Attempted",
        "The Mock Bank evaluated whether the payment request matched a valid clearance token.",
        {
            "run_id": payment_request.run_id,
            "token_id": payment_request.token_id,
            "amount": payment_request.amount,
            "bank_account_last4": payment_request.bank_account_last4,
        },
    )

    execution_result = attempt_mock_bank_execution(
        payment_request,
        token=clearance_token,
        secret=active_config.token_secret,
        now=active_config.now,
        expected_packet_hash=proof_packet.proof_hash(),
        expected_ledger_entry_hash=ledger_entry.entry_hash,
    )

    if execution_result.accepted:
        timeline_builder.add(
            EventType.EXECUTION_ACCEPTED.value,
            "Execution Accepted",
            "The Mock Bank accepted the payment because the clearance token matched exactly.",
            {
                "execution_reference": execution_result.execution_reference,
                "reason_code": execution_result.reason_code,
            },
        )
    else:
        timeline_builder.add(
            EventType.EXECUTION_REJECTED.value,
            "Execution Rejected",
            "The Mock Bank rejected the payment because the enforcement check failed.",
            {
                "reason_code": execution_result.reason_code,
                "human_reason": execution_result.human_reason,
            },
        )

    timeline = timeline_builder.build()
    return OrchestratedRun(
        scenario=seed.scenario,
        seed=seed,
        proposal=proposal,
        run_context=run_context,
        outcome=outcome,
        proof_packet=proof_packet,
        ledger_entry=ledger_entry,
        clearance_token=clearance_token,
        payment_request=payment_request,
        execution_result=execution_result,
        timeline=timeline,
    )


def run_all_demo_scenarios(
    config: OrchestratorConfig | None = None,
) -> dict[str, OrchestratedRun]:
    """Run clean, injection, and forgery scenarios against a shared ledger."""

    active_config = config or OrchestratorConfig()
    ledger = HashLedger()
    runs: dict[str, OrchestratedRun] = {}
    for scenario in ("clean", "injection", "forgery"):
        runs[scenario] = run_scenario(scenario, config=active_config, ledger=ledger)
    return runs


def summarize_orchestrated_run(run: OrchestratedRun) -> dict[str, Any]:
    """Return a compact UI-ready summary of one orchestrated run."""

    return {
        "scenario": run.scenario,
        "run_id": run.run_context.run_id,
        "final_decision": run.final_decision.value,
        "allow_execution": run.allow_execution,
        "token_issued": run.clearance_token is not None,
        "mock_bank_status": run.execution_result.status,
        "proof_hash": run.proof_packet.proof_hash(),
        "ledger_entry_hash": run.ledger_entry.entry_hash,
        "timeline_events_count": run.timeline.length,
    }
