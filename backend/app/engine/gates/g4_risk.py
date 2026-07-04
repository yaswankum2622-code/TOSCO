"""Gate G4: transactional risk signals."""

from __future__ import annotations

from app.engine.gate_engine import gate
from app.models import Decision, GateResult, GateStatus, RunContext, WorkflowDefinition


@gate("G4_RISK")
def g4_risk(ctx: RunContext, workflow: WorkflowDefinition) -> GateResult:
    """Evaluate typed risk signals without relying on raw document prose."""

    del workflow

    if ctx.signals.get("duplicate_invoice") is True:
        return GateResult(
            gate_id="G4_RISK",
            name="Risk Signals",
            status=GateStatus.FAIL,
            decision=Decision.BLOCK,
            reason_code="DUPLICATE_INVOICE",
            human_reason="Risk signals indicate this invoice duplicates an existing payment request.",
            evidence_refs=["invoice"],
        )

    if ctx.signals.get("injection_marker_detected") is True:
        return GateResult(
            gate_id="G4_RISK",
            name="Risk Signals",
            status=GateStatus.FAIL,
            decision=Decision.BLOCK,
            reason_code="INJECTION_ROUTING_RISK",
            human_reason="A typed payment-routing signal is suspicious and cannot be cleared automatically.",
            evidence_refs=["invoice", "vendor_master"],
        )

    if ctx.signals.get("velocity_risk") is True:
        return GateResult(
            gate_id="G4_RISK",
            name="Risk Signals",
            status=GateStatus.WARN,
            decision=Decision.ESCALATE,
            reason_code="PAYMENT_VELOCITY_RISK",
            human_reason="Payment velocity signals require review before automatic clearance.",
            evidence_refs=["invoice"],
        )

    bank_changed_days_ago = ctx.signals.get("bank_changed_days_ago")
    if isinstance(bank_changed_days_ago, int) and bank_changed_days_ago <= 7:
        return GateResult(
            gate_id="G4_RISK",
            name="Risk Signals",
            status=GateStatus.WARN,
            decision=Decision.ESCALATE,
            reason_code="RECENT_BANK_CHANGE",
            human_reason="The payment routes to an account with a recent bank change.",
            evidence_refs=["vendor_master"],
        )

    if ctx.signals.get("is_first_payment_to_account") is True:
        return GateResult(
            gate_id="G4_RISK",
            name="Risk Signals",
            status=GateStatus.WARN,
            decision=Decision.ESCALATE,
            reason_code="FIRST_PAYMENT_TO_ACCOUNT",
            human_reason="This would be the first payment sent to the proposed bank account.",
            evidence_refs=["vendor_master"],
        )

    return GateResult(
        gate_id="G4_RISK",
        name="Risk Signals",
        status=GateStatus.PASS,
        decision=Decision.ALLOW,
        reason_code="RISK_ACCEPTABLE",
        human_reason="Typed risk signals do not indicate elevated payment risk.",
        evidence_refs=["invoice", "vendor_master"],
    )
