"""Build deterministic proof packets from clearance outcomes."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from app.engine.pipeline import ClearanceOutcome, validate_outcome
from app.models import Decision, GateResult, RunContext, ToolCall, canonical_json_hash


_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


def _require_sha256_hex(value: str, field_name: str) -> str:
    """Reject hashes that are not lowercase SHA-256 hex digests."""

    if _SHA256_HEX_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a 64-character lowercase hex SHA-256 string")
    return value


class ProofPacketError(RuntimeError):
    """Signal proof-packet construction failures that invalidate audit claims."""


class EvidenceDigest(BaseModel):
    """Capture a document's presence and digest without storing raw document content."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    evidence_type: str
    evidence_hash: str
    present: bool = True

    @field_validator("evidence_type")
    @classmethod
    def validate_evidence_type(cls, value: str) -> str:
        """Reject blank evidence labels."""

        if not value.strip():
            raise ValueError("evidence_type cannot be empty")
        return value.strip()

    @field_validator("evidence_hash")
    @classmethod
    def validate_evidence_hash(cls, value: str) -> str:
        """Require SHA-256 hex digests for evidence payloads."""

        return _require_sha256_hex(value, "evidence_hash")


class ToolCallDigest(BaseModel):
    """Capture a tool call by digest so proofs stay compact and deterministic."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    tool_id: str
    tool_hash: str
    simulated: bool = True

    @field_validator("tool_id")
    @classmethod
    def validate_tool_id(cls, value: str) -> str:
        """Reject blank tool identifiers."""

        if not value.strip():
            raise ValueError("tool_id cannot be empty")
        return value.strip()

    @field_validator("tool_hash")
    @classmethod
    def validate_tool_hash(cls, value: str) -> str:
        """Require SHA-256 hex digests for tool calls."""

        return _require_sha256_hex(value, "tool_hash")


class GateResultDigest(BaseModel):
    """Capture the digest and summary fields of a gate result."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    gate_id: str
    result_hash: str
    decision: Decision
    reason_code: str

    @field_validator("gate_id", "reason_code")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: Any) -> str:
        """Reject blank gate digest metadata."""

        if not value.strip():
            raise ValueError(f"{info.field_name} cannot be empty")
        return value.strip()

    @field_validator("result_hash")
    @classmethod
    def validate_result_hash(cls, value: str) -> str:
        """Require SHA-256 hex digests for gate results."""

        return _require_sha256_hex(value, "result_hash")


class HumanReviewRecord(BaseModel):
    """Capture reviewer action for audit and proof linkage."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    reviewer_id: str
    approved_at: str
    action: str
    review_reason: str

    @field_validator("reviewer_id", "approved_at", "action", "review_reason")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: Any) -> str:
        if not value.strip():
            raise ValueError(f"{info.field_name} cannot be empty")
        return value.strip()


class ProofPacket(BaseModel):
    """Represent the cryptographic summary of one clearance decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    packet_version: str = "1.0"
    packet_type: str = "vendor_payment_clearance"
    run_id: str
    workflow_id: str
    intent_hash: str
    action_hash: str
    evidence_digests: list[EvidenceDigest] = Field(default_factory=list)
    extraction_hash: str | None = None
    tool_call_digests: list[ToolCallDigest] = Field(default_factory=list)
    gate_result_digests: list[GateResultDigest]
    decision_summary_hash: str
    final_decision: Decision
    allow_execution: bool
    fallback_mode: bool
    human_review: HumanReviewRecord | None = None

    @field_validator("run_id", "workflow_id", "packet_version", "packet_type")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: Any) -> str:
        """Reject blank packet identity fields."""

        if not value.strip():
            raise ValueError(f"{info.field_name} cannot be empty")
        return value.strip()

    @field_validator("intent_hash", "action_hash", "decision_summary_hash")
    @classmethod
    def validate_required_hashes(cls, value: str, info: Any) -> str:
        """Require SHA-256 hex digests for packet summary fields."""

        return _require_sha256_hex(value, info.field_name)

    @field_validator("extraction_hash")
    @classmethod
    def validate_optional_extraction_hash(cls, value: str | None) -> str | None:
        """Require valid SHA-256 hex when an extraction hash is present."""

        if value is None:
            return None
        return _require_sha256_hex(value, "extraction_hash")

    @field_validator("gate_result_digests")
    @classmethod
    def validate_gate_result_digests(cls, value: list[GateResultDigest]) -> list[GateResultDigest]:
        """Reject packets that do not summarize any gate results."""

        if not value:
            raise ValueError("gate_result_digests must not be empty")
        return value

    @model_validator(mode="after")
    def validate_execution_consistency(self) -> "ProofPacket":
        """Keep execution eligibility aligned with the final decision."""

        if self.final_decision is Decision.ALLOW and self.allow_execution is not True:
            raise ValueError("allow_execution must be True when final_decision is ALLOW")
        if self.final_decision is not Decision.ALLOW and self.allow_execution is not False:
            raise ValueError("allow_execution must be False when final_decision is not ALLOW")
        return self

    def proof_hash(self) -> str:
        """Hash the packet canonically so equal inputs always yield equal proofs."""

        return canonical_json_hash(self.model_dump(mode="json"))


def hash_evidence_value(value: Any) -> str:
    """Hash evidence payloads canonically without carrying the raw body into the proof."""

    return canonical_json_hash(value)


def build_evidence_digests(evidence: dict[str, Any]) -> list[EvidenceDigest]:
    """Summarize evidence payloads as sorted digests for deterministic proofs."""

    if not evidence:
        return []

    digests: list[EvidenceDigest] = []
    for evidence_type in sorted(evidence):
        digests.append(
            EvidenceDigest(
                evidence_type=evidence_type,
                evidence_hash=hash_evidence_value(evidence[evidence_type]),
                present=True,
            )
        )
    return digests


def build_tool_call_digests(tool_calls: list[ToolCall]) -> list[ToolCallDigest]:
    """Summarize tool calls without embedding their full request and response bodies."""

    digests: list[ToolCallDigest] = []
    for tool_call in tool_calls:
        digests.append(
            ToolCallDigest(
                tool_id=tool_call.tool_id,
                tool_hash=canonical_json_hash(tool_call.model_dump(mode="json")),
                simulated=tool_call.simulated,
            )
        )
    return digests


def build_gate_result_digests(results: list[GateResult]) -> list[GateResultDigest]:
    """Summarize gate results in order so the proof reflects the exact chain executed."""

    if not results:
        raise ProofPacketError("Cannot build gate result digests from an empty result list")

    digests: list[GateResultDigest] = []
    for result in results:
        digests.append(
            GateResultDigest(
                gate_id=result.gate_id,
                result_hash=canonical_json_hash(result.model_dump(mode="json")),
                decision=result.decision,
                reason_code=result.reason_code,
            )
        )
    return digests


def create_proof_packet(
    ctx: RunContext,
    outcome: ClearanceOutcome,
    *,
    human_review: HumanReviewRecord | None = None,
    final_decision: Decision | None = None,
    allow_execution: bool | None = None,
) -> ProofPacket:
    """Construct the deterministic proof artifact for a completed clearance outcome."""

    if ctx.run_id != outcome.run_id:
        raise ProofPacketError(
            f"RunContext run_id '{ctx.run_id}' does not match outcome run_id '{outcome.run_id}'"
        )
    if ctx.workflow_id != outcome.workflow_id:
        raise ProofPacketError(
            f"RunContext workflow_id '{ctx.workflow_id}' does not match outcome workflow_id '{outcome.workflow_id}'"
        )
    if ctx.intent.model_dump(mode="json") != outcome.intent.model_dump(mode="json"):
        raise ProofPacketError("RunContext intent does not match outcome intent")

    try:
        validated_outcome = validate_outcome(outcome)
    except Exception as exc:
        raise ProofPacketError(f"Outcome validation failed during proof construction: {exc}") from exc

    if not validated_outcome.gate_results:
        raise ProofPacketError("ProofPacket requires at least one gate result")

    resolved_decision = final_decision if final_decision is not None else validated_outcome.final_decision
    resolved_allow = (
        allow_execution
        if allow_execution is not None
        else validated_outcome.allow_execution
    )

    try:
        return ProofPacket(
            run_id=ctx.run_id,
            workflow_id=ctx.workflow_id,
            intent_hash=canonical_json_hash(ctx.intent.model_dump(mode="json")),
            action_hash=canonical_json_hash(ctx.intent.action.model_dump(mode="json")),
            evidence_digests=build_evidence_digests(ctx.evidence),
            extraction_hash=ctx.extraction.sealed_hash() if ctx.extraction is not None else None,
            tool_call_digests=build_tool_call_digests(ctx.tool_calls),
            gate_result_digests=build_gate_result_digests(validated_outcome.gate_results),
            decision_summary_hash=canonical_json_hash(
                validated_outcome.decision_summary.model_dump(mode="json")
            ),
            final_decision=resolved_decision,
            allow_execution=resolved_allow,
            fallback_mode=validated_outcome.fallback_mode,
            human_review=human_review,
        )
    except ValidationError as exc:
        raise ProofPacketError(f"ProofPacket validation failed: {exc}") from exc
