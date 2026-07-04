"""FastAPI routes exposing the deterministic TOSCO demo backend."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.schemas import (
    EventTimelineResponse,
    ProofPacketResponse,
    RunSummaryResponse,
    StartRunRequest,
    VerifyRunResponse,
    run_to_summary,
)
from app.api.state import ApiStateError, InMemoryApiState
from app.engine.workflow import WorkflowLoadError, load_workflow_registry
from app.scenarios.loader import ScenarioLoadError, load_all_scenario_seeds


class ApiRouteError(RuntimeError):
    """Signal an HTTP response body and status without leaking internals."""

    def __init__(self, status_code: int, error: str, detail: str) -> None:
        super().__init__(detail)
        self.status_code = status_code
        self.error = error
        self.detail = detail


router = APIRouter(prefix="/api")


def _backend_root() -> Path:
    """Resolve the backend root regardless of the current working directory."""

    return Path(__file__).resolve().parents[2]


def _workflows_dir() -> Path:
    """Resolve the workflows directory for API metadata endpoints."""

    return _backend_root() / "workflows"


def get_state(request: Request) -> InMemoryApiState:
    """Return the shared in-memory demo state from the FastAPI app object."""

    state = getattr(request.app.state, "tosco_state", None)
    if not isinstance(state, InMemoryApiState):
        raise ApiRouteError(
            500,
            "STATE_NOT_INITIALIZED",
            "The backend demo state is not initialized.",
        )
    return state


def _workflow_metadata(workflow: Any) -> dict[str, Any]:
    """Serialize only the workflow fields the frontend needs for the demo."""

    return {
        "workflow_id": workflow.workflow_id,
        "workflow_name": workflow.workflow_name,
        "required_evidence_types": list(workflow.required_evidence_types),
        "gates_to_run": list(workflow.gates_to_run),
        "tools_to_call": list(workflow.tools_to_call),
        "execution_adapter": workflow.execution_adapter,
    }


def _scenario_metadata(seed: Any) -> dict[str, Any]:
    """Serialize scenario listing metadata without leaking seed internals."""

    return {
        "scenario": seed.scenario,
        "title": seed.title,
        "description": seed.description,
        "expected_naive_agent_action": seed.expected_naive_agent_action,
        "expected_tosco_decision": seed.expected_tosco_decision.value,
    }


def _raise_state_error(exc: ApiStateError) -> None:
    """Map API state errors into route-level HTTP errors."""

    raise ApiRouteError(exc.status_code, exc.error, exc.detail) from exc


@router.get("/health")
def health() -> dict[str, str]:
    """Report a static demo health payload for the frontend."""

    return {
        "status": "ok",
        "service": "TOSCO",
        "version": "0.1.0",
        "mode": "demo",
    }


@router.get("/workflows")
def list_workflows() -> list[dict[str, Any]]:
    """List loadable workflow metadata from the workflows directory."""

    try:
        registry = load_workflow_registry(_workflows_dir())
    except WorkflowLoadError as exc:
        raise ApiRouteError(
            500,
            "WORKFLOW_LOAD_FAILED",
            "Workflow metadata could not be loaded.",
        ) from exc

    return [_workflow_metadata(workflow) for workflow in registry.values()]


@router.get("/scenarios")
def list_scenarios() -> list[dict[str, Any]]:
    """List deterministic demo scenario metadata in seeded order."""

    try:
        seeds = load_all_scenario_seeds()
    except ScenarioLoadError as exc:
        raise ApiRouteError(
            500,
            "SCENARIO_LOAD_FAILED",
            "Scenario metadata could not be loaded.",
        ) from exc

    return [_scenario_metadata(seed) for seed in seeds.values()]


@router.post("/runs/start", response_model=RunSummaryResponse)
def start_run(
    payload: StartRunRequest,
    state: InMemoryApiState = Depends(get_state),
) -> RunSummaryResponse:
    """Start one scenario run using the shared in-memory ledger."""

    try:
        record = state.start_run(payload.scenario)
    except ApiStateError as exc:
        _raise_state_error(exc)

    return run_to_summary(record.orchestrated_run)


@router.get("/runs", response_model=list[RunSummaryResponse])
def list_runs(state: InMemoryApiState = Depends(get_state)) -> list[RunSummaryResponse]:
    """Return summaries for all stored demo runs."""

    return [run_to_summary(record.orchestrated_run) for record in state.list_runs()]


@router.get("/runs/{run_id}", response_model=RunSummaryResponse)
def get_run(
    run_id: str,
    state: InMemoryApiState = Depends(get_state),
) -> RunSummaryResponse:
    """Return one stored run summary by run_id."""

    try:
        record = state.get_run(run_id)
    except ApiStateError as exc:
        _raise_state_error(exc)

    return run_to_summary(record.orchestrated_run)


@router.get("/runs/{run_id}/events", response_model=EventTimelineResponse)
def get_run_events(
    run_id: str,
    state: InMemoryApiState = Depends(get_state),
) -> EventTimelineResponse:
    """Return the ordered timeline for one stored run."""

    try:
        record = state.get_run(run_id)
    except ApiStateError as exc:
        _raise_state_error(exc)

    return EventTimelineResponse(
        run_id=record.run_id,
        events=list(record.orchestrated_run.timeline.events),
    )


@router.get("/runs/{run_id}/proof", response_model=ProofPacketResponse)
def get_run_proof(
    run_id: str,
    state: InMemoryApiState = Depends(get_state),
) -> ProofPacketResponse:
    """Return the sealed proof packet for one stored run."""

    try:
        record = state.get_run(run_id)
    except ApiStateError as exc:
        _raise_state_error(exc)

    return ProofPacketResponse(
        run_id=record.run_id,
        proof_packet=record.orchestrated_run.proof_packet,
        proof_hash=record.orchestrated_run.proof_packet.proof_hash(),
        ledger_entry_hash=record.orchestrated_run.ledger_entry.entry_hash,
    )


@router.get("/runs/{run_id}/verify", response_model=VerifyRunResponse)
def verify_run(
    run_id: str,
    state: InMemoryApiState = Depends(get_state),
) -> VerifyRunResponse:
    """Live-verify one run's proof against the shared ledger."""

    try:
        verification = state.verify_run(run_id)
    except ApiStateError as exc:
        _raise_state_error(exc)

    return VerifyRunResponse.model_validate(verification)


@router.post("/runs/{run_id}/tamper-demo", response_model=VerifyRunResponse)
def tamper_run(
    run_id: str,
    state: InMemoryApiState = Depends(get_state),
) -> VerifyRunResponse:
    """Mutate one ledger row for the demo and return the failed verification state."""

    try:
        verification = state.tamper_run(run_id)
    except ApiStateError as exc:
        _raise_state_error(exc)

    return VerifyRunResponse.model_validate(verification)


@router.post("/reset")
def reset_demo(state: InMemoryApiState = Depends(get_state)) -> dict[str, Any]:
    """Reset runs and the shared ledger to a fresh demo state."""

    state.reset()
    return {
        "status": "reset",
        "runs": 0,
    }
