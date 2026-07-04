"""Fold deterministic gate results into one final clearance decision."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.models import Decision, GateResult, more_severe


class DecisionFoldError(RuntimeError):
    """Signal that gate results could not be folded into a valid final decision."""


class DecisionSummary(BaseModel):
    """Describe the final decision, its status, and the reasons that produced it."""

    model_config = ConfigDict(extra="forbid")

    final_decision: Decision
    status: str
    reason_codes: list[str] = Field(default_factory=list)
    blocking_gate_ids: list[str] = Field(default_factory=list)
    escalation_gate_ids: list[str] = Field(default_factory=list)
    allow_execution: bool
    human_summary: str


_STATUS_BY_DECISION: dict[Decision, str] = {
    Decision.ALLOW: "CLEARED",
    Decision.REQUEST_MORE_EVIDENCE: "NEEDS_EVIDENCE",
    Decision.ESCALATE: "ESCALATED",
    Decision.BLOCK: "BLOCKED",
    Decision.FREEZE: "FROZEN",
    Decision.SIMULATE_ONLY: "SIMULATE_ONLY",
}

_HUMAN_SUMMARY_BY_DECISION: dict[Decision, str] = {
    Decision.ALLOW: "All required clearance gates passed. The action is eligible for sandbox execution.",
    Decision.REQUEST_MORE_EVIDENCE: "The action cannot be cleared because required evidence or grounded extraction is missing.",
    Decision.ESCALATE: "The action requires human review before execution.",
    Decision.BLOCK: "The action is blocked because one or more clearance gates failed.",
    Decision.FREEZE: "The action is frozen because high-risk reality signals failed.",
    Decision.SIMULATE_ONLY: "The action is simulation-only and cannot execute.",
}


def fold_gate_results(results: list[GateResult]) -> DecisionSummary:
    """Fold gate decisions in order so the engine produces one deterministic verdict."""

    if not results:
        raise DecisionFoldError("Cannot fold an empty gate result list")

    final_decision = Decision.ALLOW
    reason_codes: list[str] = []
    blocking_gate_ids: list[str] = []
    escalation_gate_ids: list[str] = []

    for result in results:
        if not isinstance(result, GateResult):
            raise DecisionFoldError("Gate result sequence contains an invalid item")

        final_decision = more_severe(final_decision, result.decision)
        reason_codes.append(result.reason_code)

        if result.decision in {Decision.BLOCK, Decision.FREEZE}:
            blocking_gate_ids.append(result.gate_id)
        if result.decision in {Decision.ESCALATE, Decision.REQUEST_MORE_EVIDENCE}:
            escalation_gate_ids.append(result.gate_id)

    try:
        status = _STATUS_BY_DECISION[final_decision]
        human_summary = _HUMAN_SUMMARY_BY_DECISION[final_decision]
    except KeyError as exc:
        raise DecisionFoldError(
            f"Decision '{final_decision}' does not have a fold summary mapping"
        ) from exc

    return DecisionSummary(
        final_decision=final_decision,
        status=status,
        reason_codes=reason_codes,
        blocking_gate_ids=blocking_gate_ids,
        escalation_gate_ids=escalation_gate_ids,
        allow_execution=is_execution_allowed_for_decision(final_decision),
        human_summary=human_summary,
    )


def is_execution_allowed(summary: DecisionSummary) -> bool:
    """Expose whether the folded decision is eligible for execution."""

    return is_execution_allowed_for_decision(summary.final_decision)


def is_execution_allowed_for_decision(decision: Decision) -> bool:
    """Keep the execution-allowed rule explicit and shared across the engine."""

    return decision is Decision.ALLOW
