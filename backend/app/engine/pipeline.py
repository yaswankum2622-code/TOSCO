"""Run the in-memory deterministic clearance pipeline."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.engine.decision import DecisionFoldError, DecisionSummary, fold_gate_results
from app.engine.gate_engine import GateExecutionError, register_builtin_gates, run_gate_chain
from app.models import ActionIntent, Decision, GateResult, RunContext, WorkflowDefinition


class ClearancePipelineError(RuntimeError):
    """Signal that the clearance pipeline produced an invalid or unusable outcome."""


class ClearanceOutcome(BaseModel):
    """Capture the in-memory result of a deterministic clearance run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    workflow_id: str
    intent: ActionIntent
    gate_results: list[GateResult] = Field(default_factory=list)
    decision_summary: DecisionSummary
    final_decision: Decision
    allow_execution: bool
    fallback_mode: bool


def run_clearance(ctx: RunContext, workflow: WorkflowDefinition) -> ClearanceOutcome:
    """Execute the deterministic gate and decision path without mutating the caller."""

    if ctx.workflow_id != workflow.workflow_id:
        raise ClearancePipelineError(
            f"RunContext workflow_id '{ctx.workflow_id}' does not match workflow '{workflow.workflow_id}'"
        )

    register_builtin_gates()

    try:
        gate_results = run_gate_chain(ctx, workflow)
        decision_summary = fold_gate_results(gate_results)
    except (GateExecutionError, DecisionFoldError) as exc:
        raise ClearancePipelineError(f"Clearance pipeline failed: {exc}") from exc

    outcome = ClearanceOutcome(
        run_id=ctx.run_id,
        workflow_id=workflow.workflow_id,
        intent=ctx.intent,
        gate_results=gate_results,
        decision_summary=decision_summary,
        final_decision=decision_summary.final_decision,
        allow_execution=decision_summary.allow_execution,
        fallback_mode=ctx.fallback_mode,
    )

    return validate_outcome(outcome)


def validate_outcome(outcome: ClearanceOutcome) -> ClearanceOutcome:
    """Reject inconsistent outcomes before later units consume them."""

    if not outcome.gate_results:
        raise ClearancePipelineError("ClearanceOutcome must include at least one gate result")

    if outcome.final_decision != outcome.decision_summary.final_decision:
        raise ClearancePipelineError(
            "ClearanceOutcome final_decision does not match decision_summary.final_decision"
        )

    if outcome.allow_execution != outcome.decision_summary.allow_execution:
        raise ClearancePipelineError(
            "ClearanceOutcome allow_execution does not match decision_summary.allow_execution"
        )

    return outcome
