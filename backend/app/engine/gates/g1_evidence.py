"""Gate G1: required evidence completeness."""

from __future__ import annotations

from typing import Any

from app.engine.gate_engine import gate
from app.models import Decision, GateResult, GateStatus, RunContext, WorkflowDefinition


def _missing_evidence(value: Any) -> bool:
    """Treat absent or empty evidence payloads as missing for deterministic gating."""

    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, (dict, list, tuple, set)):
        return len(value) == 0
    return False


@gate("G1_EVIDENCE")
def g1_evidence(ctx: RunContext, workflow: WorkflowDefinition) -> GateResult:
    """Reject runs that do not have the evidence the workflow requires."""

    missing_types = [
        evidence_type
        for evidence_type in workflow.required_evidence_types
        if _missing_evidence(ctx.evidence.get(evidence_type))
    ]

    if missing_types:
        missing_text = ", ".join(missing_types)
        return GateResult(
            gate_id="G1_EVIDENCE",
            name="Evidence Completeness",
            status=GateStatus.FAIL,
            decision=Decision.REQUEST_MORE_EVIDENCE,
            reason_code="MISSING_REQUIRED_EVIDENCE",
            human_reason=f"Missing required evidence types: {missing_text}.",
            evidence_refs=missing_types,
        )

    return GateResult(
        gate_id="G1_EVIDENCE",
        name="Evidence Completeness",
        status=GateStatus.PASS,
        decision=Decision.ALLOW,
        reason_code="EVIDENCE_COMPLETE",
        human_reason="All required evidence is present.",
        evidence_refs=list(workflow.required_evidence_types),
    )
