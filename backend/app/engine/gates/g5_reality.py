"""Gate G5: external-reality confirmation."""

from __future__ import annotations

from app.engine.gate_engine import gate
from app.models import Decision, GateResult, GateStatus, RunContext, WorkflowDefinition


@gate("G5_REALITY")
def g5_reality(ctx: RunContext, workflow: WorkflowDefinition) -> GateResult:
    """Require reality signals that a forged internal document pack cannot fake."""

    bank_owner_matches_vendor = ctx.signals.get("bank_owner_matches_vendor")
    request_domain_age_days = ctx.signals.get("request_domain_age_days")
    logistics_confirmed = ctx.signals.get("logistics_confirmed")

    missing_signals: list[str] = []
    if bank_owner_matches_vendor is None:
        missing_signals.append("bank_owner_matches_vendor")
    if request_domain_age_days is None:
        missing_signals.append("request_domain_age_days")
    if logistics_confirmed is None:
        missing_signals.append("logistics_confirmed")

    if missing_signals:
        missing_text = ", ".join(missing_signals)
        return GateResult(
            gate_id="G5_REALITY",
            name="Reality Gate",
            status=GateStatus.WARN,
            decision=Decision.ESCALATE,
            reason_code="REALITY_SIGNALS_INCOMPLETE",
            human_reason=f"Reality confirmation is incomplete because these signals are missing: {missing_text}.",
            evidence_refs=["vendor_master"],
        )

    failed_signals: list[str] = []
    if bank_owner_matches_vendor is False:
        failed_signals.append("bank owner does not match vendor")
    if isinstance(request_domain_age_days, int) and request_domain_age_days <= 30:
        failed_signals.append("request domain is too new")
    if logistics_confirmed is False:
        failed_signals.append("logistics confirmation missing")

    if failed_signals:
        threshold = workflow.decision_policy.reality_required_above
        decision = Decision.BLOCK
        reason_code = "REALITY_SIGNALS_FAILED"
        if (
            bank_owner_matches_vendor is False
            and ctx.intent.action.amount >= threshold
        ):
            decision = Decision.FREEZE
            reason_code = "REALITY_OWNER_MISMATCH_FREEZE"

        failed_text = "; ".join(failed_signals)
        return GateResult(
            gate_id="G5_REALITY",
            name="Reality Gate",
            status=GateStatus.FAIL,
            decision=decision,
            reason_code=reason_code,
            human_reason=(
                "Documents are internally consistent, but reality does not confirm them: "
                f"{failed_text}."
            ),
            evidence_refs=["vendor_master"],
        )

    return GateResult(
        gate_id="G5_REALITY",
        name="Reality Gate",
        status=GateStatus.PASS,
        decision=Decision.ALLOW,
        reason_code="REALITY_CONFIRMED",
        human_reason="Independent reality signals confirm the payment instructions.",
        evidence_refs=["vendor_master"],
    )
