from __future__ import annotations

from pathlib import Path

from app.engine.pipeline import run_clearance
from app.engine.review import requires_human_review
from app.engine.workflow import load_workflow_definition
from app.models import Decision
from tests.test_gate_engine import build_context, build_signals


def load_workflow():
    return load_workflow_definition(
        Path(__file__).resolve().parents[1] / "workflows" / "vendor_payment.yaml"
    )


def test_requires_human_review_for_escalate() -> None:
    workflow = load_workflow()
    ctx = build_context(
        signals=build_signals(
            is_first_payment_to_account=True,
            bank_owner_matches_vendor=True,
            request_domain_age_days=2200,
            logistics_confirmed=True,
        ),
    )
    outcome = run_clearance(ctx, workflow)

    needs_review, reason = requires_human_review(outcome)

    assert outcome.final_decision is Decision.ESCALATE
    assert needs_review is True
    assert "human review" in reason.lower()


def test_requires_human_review_false_for_allow() -> None:
    workflow = load_workflow()
    ctx = build_context()
    outcome = run_clearance(ctx, workflow)

    needs_review, reason = requires_human_review(outcome)

    assert outcome.final_decision is Decision.ALLOW
    assert needs_review is False
    assert reason == ""
