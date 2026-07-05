"""FastAPI request and response models for the TOSCO demo backend."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.custom.builder import CustomRunInput
from app.engine.proof import ProofPacket
from app.models import ActionIntent, GateResult, ProposedAction, ToolCall, WorkflowDefinition
from app.orchestrator.events import OrchestratorEvent
from app.orchestrator.runner import OrchestratedRun


def _require_non_empty(value: str, field_name: str) -> str:
    """Reject blank API schema strings."""

    trimmed = value.strip()
    if not trimmed:
        raise ValueError(f"{field_name} cannot be empty")
    return trimmed


class StartRunRequest(BaseModel):
    """Request body for starting one deterministic demo run."""

    model_config = ConfigDict(extra="forbid")

    scenario: str
    use_vultr: bool = False

    @field_validator("scenario")
    @classmethod
    def validate_scenario(cls, value: str) -> str:
        """Reject blank scenario names."""

        return _require_non_empty(value, "scenario")


class CustomRunRequest(CustomRunInput):
    """Request body for starting one judge-supplied custom clearance run."""

    pass


class RunHandleResponse(BaseModel):
    """Minimal contract response for creating a run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        """Reject blank run identifiers."""

        return _require_non_empty(value, "run_id")


class AgentProposeRequest(BaseModel):
    """Contract request body for the public proposal endpoint."""

    model_config = ConfigDict(extra="forbid")

    agent_id: str
    workflow: str
    action: ProposedAction
    evidence_refs: list[str] = Field(default_factory=list)
    declared_confidence: float
    requested_mode: str
    scenario: str

    @field_validator("agent_id", "workflow", "requested_mode", "scenario")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank proposal fields."""

        return _require_non_empty(value, info.field_name)

    @field_validator("declared_confidence")
    @classmethod
    def validate_declared_confidence(cls, value: float) -> float:
        """Keep confidence values within the documented 0..1 range."""

        if not 0 <= value <= 1:
            raise ValueError("declared_confidence must be between 0 and 1")
        return value


class AgentProposeResponse(BaseModel):
    """Contract response for a proposal that was accepted for consideration."""

    model_config = ConfigDict(extra="forbid")

    intent_id: str
    accepted: bool

    @field_validator("intent_id")
    @classmethod
    def validate_intent_id(cls, value: str) -> str:
        """Reject blank intent identifiers."""

        return _require_non_empty(value, "intent_id")


class RunSummaryResponse(BaseModel):
    """Compact summary of one orchestrated run for list and detail views."""

    model_config = ConfigDict(extra="forbid")

    scenario: str
    run_id: str
    final_decision: str
    allow_execution: bool
    token_issued: bool
    mock_bank_status: str
    mock_bank_reason_code: str
    proof_hash: str
    ledger_entry_hash: str
    timeline_events_count: int

    @field_validator(
        "scenario",
        "run_id",
        "final_decision",
        "mock_bank_status",
        "mock_bank_reason_code",
        "proof_hash",
        "ledger_entry_hash",
    )
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank summary fields."""

        return _require_non_empty(value, info.field_name)


class EventTimelineResponse(BaseModel):
    """Serialized event timeline for one stored run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    events: list[OrchestratorEvent]

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        """Reject blank run identifiers."""

        return _require_non_empty(value, "run_id")


class RunSnapshotResponse(BaseModel):
    """Full run snapshot used by the documented poll-fallback endpoint."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    workflow_id: str | None = None
    status: str
    intent: ActionIntent | None = None
    evidence_refs: list[str] = Field(default_factory=list)
    extraction_hash: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    gate_results: list[GateResult] = Field(default_factory=list)
    decision: str | None = None
    fallback_mode: bool = False
    clearance_token: str | None = None
    review_reason: str | None = None
    error_message: str | None = None

    @field_validator("run_id", "status")
    @classmethod
    def validate_required_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank snapshot identifiers."""

        return _require_non_empty(value, info.field_name)

    @field_validator("workflow_id", "decision", "clearance_token", "error_message", "review_reason")
    @classmethod
    def validate_optional_strings(
        cls,
        value: str | None,
        info: ValidationInfo,
    ) -> str | None:
        """Trim optional strings while preserving nullability."""

        if value is None:
            return None
        return _require_non_empty(value, info.field_name)


class ProofPacketResponse(BaseModel):
    """Expose the sealed proof packet plus proof linkage hashes."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    proof_packet: ProofPacket
    proof_hash: str
    ledger_entry_hash: str

    @field_validator("run_id", "proof_hash", "ledger_entry_hash")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank proof response fields."""

        return _require_non_empty(value, info.field_name)


class VerifyRunResponse(BaseModel):
    """Expose live proof and ledger verification status for one run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    ledger_chain_valid: bool
    packet_entry_valid: bool
    proof_hash: str
    ledger_entry_hash: str
    verified: bool
    chain_head: str | None = None
    tampered_field: str | None = None
    verify_now: bool | None = None
    broken_record_index: int | None = None

    @field_validator("run_id", "proof_hash", "ledger_entry_hash")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank verification fields."""

        return _require_non_empty(value, info.field_name)

    @field_validator("chain_head", "tampered_field")
    @classmethod
    def validate_optional_strings(
        cls,
        value: str | None,
        info: ValidationInfo,
    ) -> str | None:
        """Trim optional verification metadata while preserving nullability."""

        if value is None:
            return None
        return _require_non_empty(value, info.field_name)


class ErrorResponse(BaseModel):
    """Stable error body for predictable frontend handling."""

    model_config = ConfigDict(extra="forbid")

    error_code: str
    message: str
    error: str
    detail: str

    @field_validator("error_code", "message", "error", "detail")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank error fields."""

        return _require_non_empty(value, info.field_name)


class VultrStatusResponse(BaseModel):
    """Safe integration-status payload that never exposes a raw API key."""

    model_config = ConfigDict(extra="forbid")

    configured: bool
    base_url: str
    model: str
    mode: str
    key_present: bool

    @field_validator("base_url", "model", "mode")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank Vultr status metadata."""

        return _require_non_empty(value, info.field_name)


class ReviewRunRequest(BaseModel):
    """Request body for submitting human review on a paused run."""

    model_config = ConfigDict(extra="forbid")

    reviewer_id: str
    action: str

    @field_validator("reviewer_id", "action")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank review fields."""

        return _require_non_empty(value, info.field_name)


class ExecutionAttemptRequest(BaseModel):
    """Contract request body for the public execution-boundary endpoint."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    token: str | None = None
    vendor_id: str
    amount: float

    @field_validator("run_id", "vendor_id")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank execution request identifiers."""

        return _require_non_empty(value, info.field_name)

    @field_validator("token")
    @classmethod
    def validate_optional_token(cls, value: str | None) -> str | None:
        """Collapse blank token strings into None."""

        if value is None:
            return None
        trimmed = value.strip()
        return trimmed or None

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: float) -> float:
        """Reject non-positive execution amounts."""

        if value <= 0:
            raise ValueError("amount must be > 0")
        return value


class ExecutionAttemptResponse(BaseModel):
    """Contract response for the public execution-boundary endpoint."""

    model_config = ConfigDict(extra="forbid")

    executed: bool
    reason: str

    @field_validator("reason")
    @classmethod
    def validate_reason(cls, value: str) -> str:
        """Reject blank execution reasons."""

        return _require_non_empty(value, "reason")


def run_to_summary(orchestrated_run: OrchestratedRun) -> RunSummaryResponse:
    """Convert a stored orchestrated run into the API summary shape."""

    if (
        orchestrated_run.awaiting_review
        or orchestrated_run.execution_result is None
        or orchestrated_run.proof_packet is None
        or orchestrated_run.ledger_entry is None
    ):
        raise ValueError("Run summary is unavailable until review and finalization complete.")

    return RunSummaryResponse(
        scenario=orchestrated_run.scenario,
        run_id=orchestrated_run.run_context.run_id,
        final_decision=orchestrated_run.proof_packet.final_decision.value,
        allow_execution=orchestrated_run.proof_packet.allow_execution,
        token_issued=orchestrated_run.clearance_token is not None,
        mock_bank_status=orchestrated_run.execution_result.status,
        mock_bank_reason_code=orchestrated_run.execution_result.reason_code,
        proof_hash=orchestrated_run.proof_packet.proof_hash(),
        ledger_entry_hash=orchestrated_run.ledger_entry.entry_hash,
        timeline_events_count=orchestrated_run.timeline.length,
    )


def workflow_to_contract_payload(workflow: WorkflowDefinition) -> dict[str, object]:
    """Serialize a workflow definition using the public contract field names."""

    return workflow.model_dump(mode="json")
