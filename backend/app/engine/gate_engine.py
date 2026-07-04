"""Register and execute deterministic clearance gates."""

from __future__ import annotations

from collections.abc import Callable
from importlib import import_module

from app.models import GateResult, RunContext, WorkflowDefinition


class GateExecutionError(RuntimeError):
    """Signal gate registration or execution failures that must stop the engine."""


GateFn = Callable[[RunContext, WorkflowDefinition], GateResult]

REGISTRY: dict[str, GateFn] = {}

_BUILTIN_GATE_IDS = frozenset(
    {
        "G1_EVIDENCE",
        "G2_GROUNDEDNESS",
        "G3_POLICY",
        "G4_RISK",
        "G5_REALITY",
        "G6_DECISION_SEAL",
    }
)

_BUILTIN_GATE_MODULES = (
    "app.engine.gates.g1_evidence",
    "app.engine.gates.g2_groundedness",
    "app.engine.gates.g3_policy",
    "app.engine.gates.g4_risk",
    "app.engine.gates.g5_reality",
    "app.engine.gates.g6_decision_seal",
)


def gate(gate_id: str) -> Callable[[GateFn], GateFn]:
    """Register a gate function under a stable ID used by workflow config."""

    normalized_gate_id = gate_id.strip()
    if not normalized_gate_id:
        raise GateExecutionError("gate_id cannot be empty")

    def decorator(func: GateFn) -> GateFn:
        if normalized_gate_id in REGISTRY:
            raise GateExecutionError(f"Gate '{normalized_gate_id}' is already registered")
        REGISTRY[normalized_gate_id] = func
        return func

    return decorator


def register_builtin_gates() -> None:
    """Ensure the built-in deterministic gates are available before execution."""

    for module_name in _BUILTIN_GATE_MODULES:
        import_module(module_name)

    missing_gate_ids = _BUILTIN_GATE_IDS - set(REGISTRY)
    if missing_gate_ids:
        missing_text = ", ".join(sorted(missing_gate_ids))
        raise GateExecutionError(f"Built-in gate registration is incomplete: {missing_text}")


def available_gate_ids() -> set[str]:
    """Expose the current registry because workflow validation depends on it."""

    register_builtin_gates()
    return set(REGISTRY)


def get_gate(gate_id: str) -> GateFn:
    """Resolve a gate by ID so workflows execute only registered logic."""

    register_builtin_gates()
    try:
        return REGISTRY[gate_id]
    except KeyError as exc:
        raise GateExecutionError(f"Unknown gate ID: {gate_id}") from exc


def run_gate(gate_id: str, ctx: RunContext, workflow: WorkflowDefinition) -> GateResult:
    """Execute one gate and verify it returned the declared typed result."""

    gate_fn = get_gate(gate_id)
    try:
        result = gate_fn(ctx, workflow)
    except GateExecutionError:
        raise
    except Exception as exc:
        raise GateExecutionError(f"Gate '{gate_id}' execution failed: {exc}") from exc

    if not isinstance(result, GateResult):
        raise GateExecutionError(f"Gate '{gate_id}' returned an invalid result type")
    if result.gate_id != gate_id:
        raise GateExecutionError(
            f"Gate '{gate_id}' returned mismatched gate_id '{result.gate_id}'"
        )
    return result


def _copy_run_context_for_chain(ctx: RunContext) -> RunContext:
    """Create an isolated run context for gate chaining without deep-copying sealed data."""

    return RunContext(
        run_id=ctx.run_id,
        intent=ctx.intent,
        workflow_id=ctx.workflow_id,
        extraction=ctx.extraction,
        evidence=dict(ctx.evidence),
        signals=dict(ctx.signals),
        tool_calls=list(ctx.tool_calls),
        results=[],
        fallback_mode=ctx.fallback_mode,
    )


def run_gate_chain(ctx: RunContext, workflow: WorkflowDefinition) -> list[GateResult]:
    """Execute the configured gate chain without mutating the caller's run context."""

    working_ctx = _copy_run_context_for_chain(ctx)
    results: list[GateResult] = []

    for gate_id in workflow.gates_to_run:
        try:
            result = run_gate(gate_id, working_ctx, workflow)
        except GateExecutionError as exc:
            raise GateExecutionError(
                f"Gate chain execution failed at '{gate_id}': {exc}"
            ) from exc
        results.append(result)
        working_ctx.results.append(result)

    return results
