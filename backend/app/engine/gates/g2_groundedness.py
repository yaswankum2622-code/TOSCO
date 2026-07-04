"""Gate G2: sealed extraction grounding and bank consistency."""

from __future__ import annotations

from app.engine.gate_engine import gate
from app.models import Decision, GateResult, GateStatus, RunContext, WorkflowDefinition


def _vendor_master_bank_last4(ctx: RunContext) -> str | None:
    """Read registered bank details from typed vendor master evidence only."""

    vendor_master = ctx.evidence.get("vendor_master")
    if not isinstance(vendor_master, dict):
        return None

    raw_value = vendor_master.get("registered_bank_last4")
    if isinstance(raw_value, str) and raw_value.strip():
        return raw_value.strip()
    return None


@gate("G2_GROUNDEDNESS")
def g2_groundedness(ctx: RunContext, workflow: WorkflowDefinition) -> GateResult:
    """Require grounded extracted fields and typed bank-account consistency."""

    if ctx.extraction is None:
        return GateResult(
            gate_id="G2_GROUNDEDNESS",
            name="Grounded Extraction",
            status=GateStatus.FAIL,
            decision=Decision.REQUEST_MORE_EVIDENCE,
            reason_code="EXTRACTION_NOT_SEALED",
            human_reason="No sealed extraction is available for grounded review.",
            evidence_refs=["invoice"],
        )

    required_fields = workflow.extraction_schema.get("required_fields", [])
    missing_grounding: list[str] = []
    for field_name in required_fields:
        field_value = ctx.extraction.fields.get(field_name)
        source_spans = ctx.extraction.source_spans.get(field_name)
        if field_value is None or not source_spans:
            missing_grounding.append(field_name)

    if missing_grounding:
        missing_text = ", ".join(missing_grounding)
        return GateResult(
            gate_id="G2_GROUNDEDNESS",
            name="Grounded Extraction",
            status=GateStatus.FAIL,
            decision=Decision.REQUEST_MORE_EVIDENCE,
            reason_code="UNGROUNDED_EXTRACTION",
            human_reason=f"Required extracted fields are not grounded to source spans: {missing_text}.",
            evidence_refs=["invoice"],
        )

    extracted_bank_last4 = ctx.extraction.fields.get("bank_account_last4")
    proposed_bank_last4 = ctx.intent.action.bank_account_last4
    vendor_master_bank_last4 = _vendor_master_bank_last4(ctx)

    if extracted_bank_last4 != proposed_bank_last4:
        return GateResult(
            gate_id="G2_GROUNDEDNESS",
            name="Grounded Extraction",
            status=GateStatus.FAIL,
            decision=Decision.BLOCK,
            reason_code="BANK_ACCOUNT_MISMATCH",
            human_reason=(
                "The sealed bank account does not match the proposed payment account."
            ),
            evidence_refs=["invoice", "vendor_master"],
        )

    if vendor_master_bank_last4 is not None and extracted_bank_last4 != vendor_master_bank_last4:
        return GateResult(
            gate_id="G2_GROUNDEDNESS",
            name="Grounded Extraction",
            status=GateStatus.FAIL,
            decision=Decision.BLOCK,
            reason_code="BANK_ACCOUNT_MISMATCH",
            human_reason=(
                "The sealed bank account does not match the vendor master's registered account."
            ),
            evidence_refs=["invoice", "vendor_master"],
        )

    return GateResult(
        gate_id="G2_GROUNDEDNESS",
        name="Grounded Extraction",
        status=GateStatus.PASS,
        decision=Decision.ALLOW,
        reason_code="FIELDS_GROUNDED",
        human_reason="Required payment fields are grounded to source spans and match typed master data.",
        evidence_refs=["invoice", "vendor_master"],
    )
