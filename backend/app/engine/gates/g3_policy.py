"""Gate G3: deterministic policy compliance."""

from __future__ import annotations

from app.engine.gate_engine import gate
from app.models import Decision, GateResult, GateStatus, RunContext, WorkflowDefinition


@gate("G3_POLICY")
def g3_policy(ctx: RunContext, workflow: WorkflowDefinition) -> GateResult:
    """Apply fixed policy rules before the run moves to risk and reality checks."""

    if ctx.signals.get("sod_violation") is True:
        return GateResult(
            gate_id="G3_POLICY",
            name="Policy Compliance",
            status=GateStatus.FAIL,
            decision=Decision.BLOCK,
            reason_code="SEGREGATION_OF_DUTIES_VIOLATION",
            human_reason="Segregation-of-duties policy was violated for this payment.",
            evidence_refs=["policy_pack"],
        )

    if (
        workflow.decision_policy.mandatory_human_confirm is True
        and ctx.signals.get("human_confirmed") is not True
    ):
        return GateResult(
            gate_id="G3_POLICY",
            name="Policy Compliance",
            status=GateStatus.WARN,
            decision=Decision.ESCALATE,
            reason_code="HUMAN_CONFIRMATION_REQUIRED",
            human_reason="Policy requires human confirmation before this payment can continue.",
            evidence_refs=["policy_pack"],
        )

    if ctx.intent.action.amount >= workflow.decision_policy.high_value_threshold:
        return GateResult(
            gate_id="G3_POLICY",
            name="Policy Compliance",
            status=GateStatus.PASS,
            decision=Decision.ALLOW,
            reason_code="HIGH_VALUE_POLICY_REQUIRES_REALITY_GATE",
            human_reason="High-value policy is satisfied pending independent verification by the Reality Gate.",
            evidence_refs=["policy_pack"],
        )

    return GateResult(
        gate_id="G3_POLICY",
        name="Policy Compliance",
        status=GateStatus.PASS,
        decision=Decision.ALLOW,
        reason_code="POLICY_COMPLIANT",
        human_reason="The payment complies with deterministic policy checks.",
        evidence_refs=["policy_pack"],
    )
