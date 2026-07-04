"""Gate G6: decision seal readiness summary."""

from __future__ import annotations

from app.engine.gate_engine import gate
from app.models import Decision, GateResult, GateStatus, RunContext, WorkflowDefinition, more_severe


@gate("G6_DECISION_SEAL")
def g6_decision_seal(ctx: RunContext, workflow: WorkflowDefinition) -> GateResult:
    """Summarize prior gate outcomes so later units can seal the final decision."""

    del workflow

    most_severe = Decision.ALLOW
    for prior_result in ctx.results:
        most_severe = more_severe(most_severe, prior_result.decision)

    evidence_refs = [result.gate_id for result in ctx.results]

    if most_severe in {Decision.BLOCK, Decision.FREEZE}:
        return GateResult(
            gate_id="G6_DECISION_SEAL",
            name="Decision Seal Readiness",
            status=GateStatus.FAIL,
            decision=most_severe,
            reason_code="DECISION_SEAL_BLOCKED",
            human_reason="The gate chain is ready to seal a blocking decision.",
            evidence_refs=evidence_refs,
        )

    if most_severe in {
        Decision.ESCALATE,
        Decision.REQUEST_MORE_EVIDENCE,
        Decision.SIMULATE_ONLY,
    }:
        return GateResult(
            gate_id="G6_DECISION_SEAL",
            name="Decision Seal Readiness",
            status=GateStatus.WARN,
            decision=most_severe,
            reason_code="DECISION_SEAL_ESCALATED",
            human_reason="The gate chain is ready to seal a non-final decision requiring review.",
            evidence_refs=evidence_refs,
        )

    return GateResult(
        gate_id="G6_DECISION_SEAL",
        name="Decision Seal Readiness",
        status=GateStatus.PASS,
        decision=Decision.ALLOW,
        reason_code="DECISION_SEAL_READY",
        human_reason="All prior gates are clear and the decision is ready to be sealed.",
        evidence_refs=evidence_refs,
    )
