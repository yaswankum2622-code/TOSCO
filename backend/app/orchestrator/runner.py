"""Run deterministic in-memory TOSCO demo scenarios end to end."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationInfo, computed_field, field_validator

from app.agent.reference_ap_agent import (
    AgentProposal,
    ReferenceAPAgent,
    build_run_context_from_agent_proposal,
)
from app.config import load_settings_from_env
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
from app.integrations.vultr import VultrExtractionResult, VultrInferenceClient, VultrSettings
from app.models import Decision, RunContext, ToolCall, WorkflowDefinition
from app.orchestrator.events import EventType, EventTimeline, TimelineBuilder
from app.scenarios.loader import ScenarioLoadError, ScenarioSeed, load_scenario_seed


ContractEventEmitter = Callable[[str, dict[str, Any] | None], None]


def _require_non_empty(value: str, field_name: str) -> str:
    """Reject blank orchestrator config fields."""

    trimmed = value.strip()
    if not trimmed:
        raise ValueError(f"{field_name} cannot be empty")
    return trimmed


class OrchestratorError(RuntimeError):
    """Signal invalid scenario orchestration state or failures."""


@dataclass(frozen=True, slots=True)
class ExtractionResolution:
    """Carry the sealed extraction plus metadata needed for public event reporting."""

    run_context: RunContext
    source: str
    latency_ms: int | None = None


class OrchestratorConfig(BaseModel):
    """Hold deterministic settings for one orchestrated demo run."""

    model_config = ConfigDict(extra="forbid")

    workflow_path: str = "backend/workflows/vendor_payment.yaml"
    token_secret: str = "local-demo-secret"
    issued_at: str = "2026-07-04T12:00:00Z"
    expires_at: str = "2026-07-04T12:10:00Z"
    now: str = "2026-07-04T12:05:00Z"
    use_vultr: bool = False
    vultr_fallback_enabled: bool = True

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


def _tool_event_payload(
    workflow: WorkflowDefinition,
    run_context: RunContext,
    tool_id: str,
) -> dict[str, Any]:
    """Build deterministic simulated tool payloads for the event timeline."""

    del workflow
    return {
        "tool_id": tool_id,
        "simulated": True,
        "signal_keys": sorted(run_context.signals.keys()),
    }


def _required_extraction_fields(workflow: WorkflowDefinition) -> list[str]:
    """Read required extraction fields from the loaded workflow definition."""

    fields = workflow.extraction_schema.get("required_fields", [])
    return [field for field in fields if isinstance(field, str) and field.strip()]


def _emit_contract_event(
    emitter: ContractEventEmitter | None,
    event_name: str,
    data: dict[str, Any] | None = None,
) -> None:
    """Emit one public-contract event when a streaming bus is attached."""

    if emitter is None:
        return
    emitter(event_name, {} if data is None else data)


def _vultr_model_name(vultr_client: Any) -> str:
    """Read a model label from a real or fake Vultr client."""

    settings = getattr(vultr_client, "settings", None)
    model_name = getattr(settings, "chat_model", None)
    if isinstance(model_name, str) and model_name.strip():
        return model_name.strip()
    return "unknown"


def _vultr_fallback_enabled(active_config: OrchestratorConfig, vultr_client: Any) -> bool:
    """Resolve whether the orchestrator may fall back after a Vultr extraction failure."""

    settings = getattr(vultr_client, "settings", None)
    client_flag = getattr(settings, "fallback_enabled", active_config.vultr_fallback_enabled)
    return active_config.vultr_fallback_enabled and bool(client_flag)


def _build_vultr_client(active_config: OrchestratorConfig) -> VultrInferenceClient:
    """Create a Vultr client from environment settings only when the caller opts in."""

    app_settings = load_settings_from_env()
    return VultrInferenceClient(
        VultrSettings(
            api_key=app_settings.vultr_api_key,
            base_url=app_settings.vultr_inference_base_url,
            chat_model=app_settings.vultr_chat_model,
            fallback_enabled=active_config.vultr_fallback_enabled and app_settings.tosco_fallback,
            use_system_trust_store=app_settings.tosco_use_system_trust_store,
            ca_bundle=app_settings.vultr_ca_bundle,
        )
    )


def _build_run_context(
    seed: ScenarioSeed,
    proposal: AgentProposal,
    *,
    extraction_fields: dict[str, Any] | None = None,
    source_spans: dict[str, list[int]] | None = None,
    extractor: str = "sandbox-fallback",
    fallback_mode: bool = True,
) -> RunContext:
    """Build a RunContext using either seeded or adapter-provided extraction content."""

    return build_run_context_from_agent_proposal(
        seed,
        proposal,
        extraction_fields=extraction_fields,
        source_spans=source_spans,
        extractor=extractor,
        fallback_mode=fallback_mode,
    )


def _resolve_run_context(
    *,
    seed: ScenarioSeed,
    proposal: AgentProposal,
    workflow: WorkflowDefinition,
    active_config: OrchestratorConfig,
    timeline_builder: TimelineBuilder,
    vultr_client: VultrInferenceClient | None,
) -> ExtractionResolution:
    """Choose seeded or Vultr-backed extraction while preserving deterministic fallback."""

    if not active_config.use_vultr:
        return ExtractionResolution(
            run_context=_build_run_context(seed, proposal),
            source="fallback",
            latency_ms=None,
        )

    required_fields = _required_extraction_fields(workflow)
    active_vultr_client = vultr_client
    if active_vultr_client is None:
        try:
            active_vultr_client = _build_vultr_client(active_config)
        except Exception as exc:  # pragma: no cover - defensive config guard
            raise OrchestratorError(f"Vultr configuration could not be loaded: {exc}") from exc

    timeline_builder.add(
        EventType.VULTR_EXTRACTION_STARTED.value,
        "Vultr Extraction Started",
        "TOSCO requested extraction-only structured fields from Vultr Serverless Inference.",
        {
            "model": _vultr_model_name(active_vultr_client),
            "required_fields": required_fields,
        },
    )

    extraction_result: VultrExtractionResult = active_vultr_client.extract_vendor_payment_fields(
        evidence=seed.evidence,
        required_fields=required_fields,
    )
    if extraction_result.ok:
        timeline_builder.add(
            EventType.VULTR_EXTRACTION_SUCCEEDED.value,
            "Vultr Extraction Succeeded",
            "Vultr returned structured extraction data, which TOSCO sealed before gating.",
            {
                "model": extraction_result.model,
                "field_names": sorted(extraction_result.fields.keys()),
                "raw_content_hash": extraction_result.raw_content_hash,
                "latency_ms": extraction_result.latency_ms,
            },
        )
        return ExtractionResolution(
            run_context=_build_run_context(
                seed,
                proposal,
                extraction_fields=extraction_result.fields,
                source_spans=extraction_result.source_spans,
                extractor="vultr-serverless-inference",
                fallback_mode=False,
            ),
            source="vultr",
            latency_ms=extraction_result.latency_ms,
        )

    if not _vultr_fallback_enabled(active_config, active_vultr_client):
        raise OrchestratorError(
            "Vultr extraction failed and fallback is disabled: "
            f"{extraction_result.error_code or 'UNKNOWN_ERROR'}"
        )

    timeline_builder.add(
        EventType.VULTR_EXTRACTION_FALLBACK.value,
        "Vultr Extraction Fallback",
        "Vultr extraction failed, so TOSCO fell back to the seeded deterministic extraction.",
        {
            "model": extraction_result.model,
            "error_code": extraction_result.error_code,
            "error_message": extraction_result.error_message,
            "fallback_used": True,
            "latency_ms": extraction_result.latency_ms,
        },
    )
    return ExtractionResolution(
        run_context=_build_run_context(seed, proposal, fallback_mode=True),
        source="fallback",
        latency_ms=extraction_result.latency_ms,
    )


def run_from_seed(
    seed: ScenarioSeed,
    *,
    config: OrchestratorConfig | None = None,
    ledger: HashLedger | None = None,
    vultr_client: VultrInferenceClient | None = None,
    contract_event_emitter: ContractEventEmitter | None = None,
    proposal: AgentProposal | None = None,
) -> OrchestratedRun:
    """Run one seeded clearance path through proposal, clearance, proof, token, and execution."""

    active_config = config or OrchestratorConfig()
    active_ledger = ledger or HashLedger()

    try:
        workflow = load_workflow_definition(_resolve_workflow_path(active_config.workflow_path))
    except Exception as exc:
        raise OrchestratorError(f"Workflow loading failed: {exc}") from exc

    if seed.workflow_id != workflow.workflow_id:
        raise OrchestratorError(
            f"Scenario workflow_id '{seed.workflow_id}' does not match loaded workflow '{workflow.workflow_id}'"
        )

    active_proposal = proposal
    if active_proposal is None:
        agent = ReferenceAPAgent()
        active_proposal = agent.propose_from_seed(seed)

    timeline_builder = TimelineBuilder(seed.run_id)
    timeline_builder.add(
        EventType.AGENT_PROPOSED.value,
        "Agent Proposed Payment",
        "The reference AP agent proposed a payment action from seeded documents.",
        {
            "scenario": seed.scenario,
            "naive_action": active_proposal.naive_action,
            "vendor_id": active_proposal.intent.action.vendor_id,
            "amount": active_proposal.intent.action.amount,
            "bank_account_last4": active_proposal.intent.action.bank_account_last4,
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
    _emit_contract_event(
        contract_event_emitter,
        EventType.PLAN_STARTED.value,
        {
            "workflow_id": workflow.workflow_id,
            "workflow_name": workflow.workflow_name,
            "gates_to_run": list(workflow.gates_to_run),
        },
    )

    evidence_types = list(workflow.required_evidence_types)
    for pass_index, evidence_type in enumerate(evidence_types, start=1):
        evidence_payload = seed.evidence.get(evidence_type)
        doc_id = None
        if isinstance(evidence_payload, dict):
            raw_doc_id = evidence_payload.get("doc_id")
            if isinstance(raw_doc_id, str) and raw_doc_id.strip():
                doc_id = raw_doc_id.strip()

        event_payload = {
            "retrieval_pass": pass_index,
            "total_passes": len(evidence_types),
            "evidence_type": evidence_type,
            "doc_id": doc_id,
            "evidence_types": list(evidence_types),
            "evidence_count": len(seed.evidence),
        }
        timeline_builder.add(
            EventType.EVIDENCE_RETRIEVED.value,
            "Evidence Loaded (Seeded)",
            "Seeded evidence was loaded for the clearance run.",
            event_payload,
        )
        _emit_contract_event(
            contract_event_emitter,
            EventType.EVIDENCE_RETRIEVED.value,
            event_payload,
        )

    extraction_resolution = _resolve_run_context(
        seed=seed,
        proposal=active_proposal,
        workflow=workflow,
        active_config=active_config,
        timeline_builder=timeline_builder,
        vultr_client=vultr_client,
    )
    run_context = extraction_resolution.run_context
    if run_context.workflow_id != workflow.workflow_id:
        raise OrchestratorError(
            f"RunContext workflow_id '{run_context.workflow_id}' does not match workflow '{workflow.workflow_id}'"
        )

    timeline_builder.add(
        EventType.EXTRACTION_STARTED.value,
        "Extraction Review Started",
        "The orchestrator prepared the sealed extraction for deterministic review.",
        {
            "extractor": run_context.extraction.extractor if run_context.extraction else "none",
            "source": extraction_resolution.source,
            "latency_ms": extraction_resolution.latency_ms,
        },
    )
    _emit_contract_event(
        contract_event_emitter,
        EventType.EXTRACTION_STARTED.value,
        {
            "extractor": run_context.extraction.extractor if run_context.extraction else "none",
            "source": extraction_resolution.source,
            "fallback_mode": run_context.fallback_mode,
            "latency_ms": extraction_resolution.latency_ms,
        },
    )
    timeline_builder.add(
        EventType.EXTRACTION_SEALED.value,
        "Extraction Sealed",
        "The extraction boundary was sealed before gates evaluated typed facts.",
        {
            "extraction_hash": run_context.extraction.sealed_hash() if run_context.extraction else None,
            "required_fields": _required_extraction_fields(workflow),
            "source": extraction_resolution.source,
            "latency_ms": extraction_resolution.latency_ms,
        },
    )
    _emit_contract_event(
        contract_event_emitter,
        EventType.EXTRACTION_SEALED.value,
        {
            "extraction_hash": run_context.extraction.sealed_hash() if run_context.extraction else None,
            "required_fields": _required_extraction_fields(workflow),
            "source": extraction_resolution.source,
            "fallback_mode": run_context.fallback_mode,
            "latency_ms": extraction_resolution.latency_ms,
        },
    )

    for tool_id in workflow.tools_to_call:
        tool_payload = _tool_event_payload(workflow, run_context, tool_id)
        run_context.tool_calls.append(
            ToolCall(
                tool_id=tool_id,
                input={"run_id": run_context.run_id},
                output=tool_payload,
                simulated=True,
            )
        )
        timeline_builder.add(
            EventType.TOOL_CALLED.value,
            "Simulated Tool Call",
            f"The orchestrator recorded a simulated call for {tool_id}.",
            tool_payload,
        )
        _emit_contract_event(contract_event_emitter, EventType.TOOL_CALLED.value, tool_payload)

    outcome = run_clearance(run_context, workflow)
    run_context.results = list(outcome.gate_results)

    for gate_result in outcome.gate_results:
        started_payload = {"gate_id": gate_result.gate_id}
        timeline_builder.add(
            EventType.GATE_STARTED.value,
            "Gate Started",
            f"{gate_result.gate_id} began deterministic evaluation.",
            started_payload,
        )
        completed_payload = {
            "gate_id": gate_result.gate_id,
            "status": gate_result.status.value,
            "decision": gate_result.decision.value,
            "reason_code": gate_result.reason_code,
        }
        timeline_builder.add(
            EventType.GATE_COMPLETED.value,
            "Gate Completed",
            f"{gate_result.gate_id} completed deterministic evaluation.",
            completed_payload,
        )
        if gate_result.gate_id != "G6_DECISION_SEAL":
            _emit_contract_event(
                contract_event_emitter,
                EventType.GATE_STARTED.value,
                started_payload,
            )
            _emit_contract_event(
                contract_event_emitter,
                EventType.GATE_COMPLETED.value,
                completed_payload,
            )

    decision_payload = {
        "final_decision": outcome.final_decision.value,
        "status": outcome.decision_summary.status,
        "allow_execution": outcome.allow_execution,
        "reason_codes": list(outcome.decision_summary.reason_codes),
    }
    timeline_builder.add(
        EventType.DECISION_MADE.value,
        "Decision Made",
        "The deterministic decision engine folded all gate results into a final verdict.",
        decision_payload,
    )
    _emit_contract_event(contract_event_emitter, EventType.DECISION_MADE.value, decision_payload)

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
        _emit_contract_event(
            contract_event_emitter,
            "TOKEN_ISSUED",
            {
                "token_id": clearance_token.token_id,
                "expires_at": clearance_token.expires_at,
                "token": clearance_token.model_dump_json(),
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

    _emit_contract_event(
        contract_event_emitter,
        EventType.PROOF_SEALED.value,
        {
            "proof_hash": proof_packet.proof_hash(),
            "final_decision": proof_packet.final_decision.value,
        },
    )

    payment_request = build_payment_request_from_context(run_context, clearance_token)
    execution_payload = {
        "run_id": payment_request.run_id,
        "token_id": payment_request.token_id,
        "amount": payment_request.amount,
        "bank_account_last4": payment_request.bank_account_last4,
    }
    timeline_builder.add(
        EventType.EXECUTION_ATTEMPTED.value,
        "Execution Attempted",
        "The Mock Bank evaluated whether the payment request matched a valid clearance token.",
        execution_payload,
    )
    _emit_contract_event(contract_event_emitter, EventType.EXECUTION_ATTEMPTED.value, execution_payload)

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
        proposal=active_proposal,
        run_context=run_context,
        outcome=outcome,
        proof_packet=proof_packet,
        ledger_entry=ledger_entry,
        clearance_token=clearance_token,
        payment_request=payment_request,
        execution_result=execution_result,
        timeline=timeline,
    )


def run_scenario(
    scenario: str,
    *,
    config: OrchestratorConfig | None = None,
    ledger: HashLedger | None = None,
    vultr_client: VultrInferenceClient | None = None,
    contract_event_emitter: ContractEventEmitter | None = None,
) -> OrchestratedRun:
    """Run one named demo scenario through proposal, clearance, proof, token, and execution."""

    try:
        seed = load_scenario_seed(scenario)
    except ScenarioLoadError as exc:
        raise OrchestratorError(f"Scenario loading failed: {exc}") from exc

    return run_from_seed(
        seed,
        config=config,
        ledger=ledger,
        vultr_client=vultr_client,
        contract_event_emitter=contract_event_emitter,
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
