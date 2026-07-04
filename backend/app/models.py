"""Typed domain models for the TOSCO clearance engine."""

from __future__ import annotations

import hashlib
import json
import re
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator


class ToscoModel(BaseModel):
    """Provide strict shared defaults for TOSCO models."""

    model_config = ConfigDict(extra="forbid")


class FrozenDict(dict[str, Any]):
    """Prevent mutation of sealed extraction dictionaries."""

    def _immutable(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("FrozenDict is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    clear = _immutable
    pop = _immutable
    popitem = _immutable
    setdefault = _immutable
    update = _immutable


class FrozenList(list[Any]):
    """Prevent mutation of sealed extraction lists."""

    def _immutable(self, *args: Any, **kwargs: Any) -> None:
        raise TypeError("FrozenList is immutable")

    __setitem__ = _immutable
    __delitem__ = _immutable
    __iadd__ = _immutable
    __imul__ = _immutable
    append = _immutable
    clear = _immutable
    extend = _immutable
    insert = _immutable
    pop = _immutable
    remove = _immutable
    reverse = _immutable
    sort = _immutable


def _freeze_value(value: Any) -> Any:
    """Return recursively immutable containers for sealed extraction content."""

    if isinstance(value, dict):
        return FrozenDict({key: _freeze_value(item) for key, item in value.items()})
    if isinstance(value, list):
        return FrozenList(_freeze_value(item) for item in value)
    return value


def _require_non_empty(value: str, field_name: str) -> str:
    """Reject blank string fields that would weaken typed invariants."""

    trimmed = value.strip()
    if not trimmed:
        raise ValueError(f"{field_name} cannot be empty")
    return trimmed


def canonical_json_hash(payload: Any) -> str:
    """Hash structured payloads canonically for deterministic comparisons."""

    canonical = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class Decision(StrEnum):
    """Enumerate every possible clearance verdict."""

    ALLOW = "ALLOW"
    ESCALATE = "ESCALATE"
    BLOCK = "BLOCK"
    REQUEST_MORE_EVIDENCE = "REQUEST_MORE_EVIDENCE"
    FREEZE = "FREEZE"
    SIMULATE_ONLY = "SIMULATE_ONLY"


_DECISION_SEVERITY = MappingProxyType(
    {
        Decision.SIMULATE_ONLY: 0,
        Decision.ALLOW: 1,
        Decision.REQUEST_MORE_EVIDENCE: 2,
        Decision.ESCALATE: 3,
        Decision.BLOCK: 4,
        Decision.FREEZE: 5,
    }
)


def decision_severity(decision: Decision) -> int:
    """Return the total-order severity rank for a decision."""

    return _DECISION_SEVERITY[decision]


def more_severe(left: Decision, right: Decision) -> Decision:
    """Pick the stricter of two decisions using the shared severity ordering."""

    return left if decision_severity(left) >= decision_severity(right) else right


class GateStatus(StrEnum):
    """Represent gate evaluation outcomes."""

    PASS = "PASS"
    WARN = "WARN"
    FAIL = "FAIL"


class ProposedAction(ToscoModel):
    """Describe the action an agent wants TOSCO to clear."""

    type: str = "payment"
    vendor_id: str
    amount: float
    currency: str = "USD"
    bank_account_last4: str

    @field_validator("type", "vendor_id")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank identifiers on proposed actions."""

        return _require_non_empty(value, info.field_name)

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: float) -> float:
        """Reject non-positive payment amounts."""

        if value <= 0:
            raise ValueError("amount must be > 0")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        """Normalize currency codes to uppercase."""

        return _require_non_empty(value, "currency").upper()

    @field_validator("bank_account_last4")
    @classmethod
    def validate_bank_account_last4(cls, value: str) -> str:
        """Require exactly four numeric characters for bank account suffixes."""

        trimmed = _require_non_empty(value, "bank_account_last4")
        if re.fullmatch(r"\d{4}", trimmed) is None:
            raise ValueError("bank_account_last4 must be exactly 4 numeric characters")
        return trimmed


class ActionIntent(ToscoModel):
    """Capture an agent's proposed action before any clearance decision exists."""

    intent_id: str
    agent_id: str
    workflow: str = "vendor_payment"
    action: ProposedAction
    evidence_refs: list[str] = Field(default_factory=list)
    declared_confidence: float = 0.0
    requested_mode: str = "assisted"

    @field_validator("intent_id", "agent_id", "workflow", "requested_mode")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank control-plane identifiers."""

        return _require_non_empty(value, info.field_name)

    @field_validator("declared_confidence")
    @classmethod
    def validate_declared_confidence(cls, value: float) -> float:
        """Keep confidence values within the documented 0..1 range."""

        if not 0 <= value <= 1:
            raise ValueError("declared_confidence must be between 0 and 1")
        return value


class SealedExtraction(ToscoModel):
    """SealedExtraction is the boundary between probabilistic extraction and deterministic clearance. Gates may read extracted fields as data, but no gate may treat model text as an instruction."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    doc_id: str
    fields: dict[str, Any]
    source_spans: dict[str, list[int]]
    extractor: str = "sandbox-fallback"

    @field_validator("doc_id", "extractor")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank extraction metadata."""

        return _require_non_empty(value, info.field_name)

    @field_validator("fields", "source_spans", mode="after")
    @classmethod
    def freeze_mapping_fields(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Freeze nested extraction content so replay cannot mutate it."""

        return _freeze_value(value)

    def sealed_hash(self) -> str:
        """Hash the sealed extraction content deterministically."""

        payload = {
            "doc_id": self.doc_id,
            "fields": self.fields,
            "source_spans": self.source_spans,
            "extractor": self.extractor,
        }
        return canonical_json_hash(payload)


class ToolCall(ToscoModel):
    """Record the typed input and output of a tool invocation."""

    tool_id: str
    input: dict[str, Any]
    output: dict[str, Any]
    simulated: bool = True
    latency_ms: int | None = None

    @field_validator("tool_id")
    @classmethod
    def validate_tool_id(cls, value: str) -> str:
        """Reject blank tool identifiers."""

        return _require_non_empty(value, "tool_id")

    @field_validator("latency_ms")
    @classmethod
    def validate_latency_ms(cls, value: int | None) -> int | None:
        """Reject negative latency values."""

        if value is not None and value < 0:
            raise ValueError("latency_ms must be >= 0")
        return value


class GateResult(ToscoModel):
    """Capture the typed outcome of a single gate evaluation."""

    gate_id: str
    name: str
    status: GateStatus
    decision: Decision
    reason_code: str
    human_reason: str
    evidence_refs: list[str] = Field(default_factory=list)

    @field_validator("gate_id", "name", "reason_code", "human_reason")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank gate metadata."""

        return _require_non_empty(value, info.field_name)


class DecisionPolicy(ToscoModel):
    """Define workflow-level thresholds that shape final decisions."""

    allow_requires_all_pass: bool = True
    high_value_threshold: float = 50000
    reality_required_above: float = 50000
    mandatory_human_confirm: bool | None = None

    @field_validator("high_value_threshold", "reality_required_above")
    @classmethod
    def validate_thresholds(cls, value: float, info: ValidationInfo) -> float:
        """Reject negative policy thresholds."""

        if value < 0:
            raise ValueError(f"{info.field_name} must be >= 0")
        return value


class WorkflowDefinition(ToscoModel):
    """Describe a workflow the clearance engine can load and execute."""

    workflow_id: str
    workflow_name: str
    required_evidence_types: list[str]
    extraction_schema: dict[str, Any]
    gates_to_run: list[str]
    tools_to_call: list[str]
    decision_policy: DecisionPolicy
    proof_packet_template: str
    execution_adapter: str = "sandbox"

    @field_validator("workflow_id", "workflow_name", "proof_packet_template", "execution_adapter")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank workflow metadata."""

        return _require_non_empty(value, info.field_name)

    @field_validator("required_evidence_types", "gates_to_run", "tools_to_call")
    @classmethod
    def validate_non_empty_lists(cls, value: list[str], info: ValidationInfo) -> list[str]:
        """Reject workflow definitions with missing required lists."""

        if not value:
            raise ValueError(f"{info.field_name} cannot be empty")
        return value

    @field_validator("required_evidence_types", "gates_to_run", "tools_to_call")
    @classmethod
    def validate_non_empty_list_entries(
        cls,
        value: list[str],
        info: ValidationInfo,
    ) -> list[str]:
        """Reject blank entries in workflow string lists."""

        if any(not item.strip() for item in value):
            raise ValueError(f"{info.field_name} cannot contain blank entries")
        return value


class RunContext(ToscoModel):
    """Hold the typed state accumulated during a clearance run."""

    run_id: str
    intent: ActionIntent
    workflow_id: str
    extraction: SealedExtraction | None = None
    evidence: dict[str, Any] = Field(default_factory=dict)
    signals: dict[str, Any] = Field(default_factory=dict)
    tool_calls: list[ToolCall] = Field(default_factory=list)
    results: list[GateResult] = Field(default_factory=list)
    fallback_mode: bool = False

    @field_validator("run_id", "workflow_id")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank run metadata."""

        return _require_non_empty(value, info.field_name)
