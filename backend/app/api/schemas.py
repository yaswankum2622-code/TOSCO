"""FastAPI request and response models for the TOSCO demo backend."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

from app.engine.proof import ProofPacket
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

    @field_validator("scenario")
    @classmethod
    def validate_scenario(cls, value: str) -> str:
        """Reject blank scenario names."""

        return _require_non_empty(value, "scenario")


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

    @field_validator("run_id", "proof_hash", "ledger_entry_hash")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank verification fields."""

        return _require_non_empty(value, info.field_name)


class ErrorResponse(BaseModel):
    """Stable error body for predictable frontend handling."""

    model_config = ConfigDict(extra="forbid")

    error: str
    detail: str

    @field_validator("error", "detail")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank error fields."""

        return _require_non_empty(value, info.field_name)


def run_to_summary(orchestrated_run: OrchestratedRun) -> RunSummaryResponse:
    """Convert a stored orchestrated run into the API summary shape."""

    return RunSummaryResponse(
        scenario=orchestrated_run.scenario,
        run_id=orchestrated_run.run_context.run_id,
        final_decision=orchestrated_run.final_decision.value,
        allow_execution=orchestrated_run.allow_execution,
        token_issued=orchestrated_run.clearance_token is not None,
        mock_bank_status=orchestrated_run.execution_result.status,
        mock_bank_reason_code=orchestrated_run.execution_result.reason_code,
        proof_hash=orchestrated_run.proof_packet.proof_hash(),
        ledger_entry_hash=orchestrated_run.ledger_entry.entry_hash,
        timeline_events_count=orchestrated_run.timeline.length,
    )
