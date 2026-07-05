"""Human-in-the-loop review gating for clearance runs."""

from __future__ import annotations

from app.engine.pipeline import ClearanceOutcome
from app.models import Decision


def requires_human_review(outcome: ClearanceOutcome) -> tuple[bool, str]:
    """Return whether a run must pause for reviewer action before token issuance."""

    if outcome.final_decision != Decision.ESCALATE:
        return False, ""

    gate_ids = outcome.decision_summary.escalation_gate_ids
    reason_codes = [
        result.reason_code
        for result in outcome.gate_results
        if result.decision is Decision.ESCALATE
    ]
    detail = ", ".join(reason_codes or gate_ids) or outcome.decision_summary.human_summary
    return True, f"Escalation requires human review: {detail}"
