"""FastAPI routes exposing the deterministic TOSCO demo backend."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Body, Depends, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import ValidationError

from app.agent.reference_ap_agent import ReferenceAPAgent
from app.api.schemas import (
    AgentProposeRequest,
    AgentProposeResponse,
    CustomRunRequest,
    ErrorResponse,
    EventTimelineResponse,
    ExecutionAttemptRequest,
    ExecutionAttemptResponse,
    ProofPacketResponse,
    RunHandleResponse,
    RunSnapshotResponse,
    RunSummaryResponse,
    StartRunRequest,
    VerifyRunResponse,
    VultrStatusResponse,
    run_to_summary,
    workflow_to_contract_payload,
)
from app.api.state import ApiStateError, InMemoryApiState
from app.config import load_settings_from_env
from app.engine.mock_bank import attempt_mock_bank_execution, build_payment_request_from_context
from app.engine.token import ClearanceToken
from app.engine.workflow import WorkflowLoadError, get_workflow, load_workflow_registry
from app.models import Decision
from app.orchestrator.runner import OrchestratorConfig
from app.scenarios.loader import ScenarioLoadError, load_all_scenario_seeds, load_scenario_seed


class ApiRouteError(RuntimeError):
    """Signal an HTTP response body and status without leaking internals."""

    def __init__(self, status_code: int, error_code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.error_code = error_code
        self.error = error_code
        self.message = message
        self.detail = message


router = APIRouter(prefix="/api")


_EXECUTION_REASON_MAP = {
    "MISSING_CLEARANCE_TOKEN": "NO_TOKEN",
    "SIGNATURE_MISMATCH": "TAMPERED_TOKEN",
    "TOKEN_DECISION_NOT_ALLOW": "NON_ALLOW_TOKEN",
    "TOKEN_EXPIRED": "EXPIRED_TOKEN",
    "VENDOR_MISMATCH": "VENDOR_MISMATCH",
    "AMOUNT_MISMATCH": "AMOUNT_MISMATCH",
    "LEDGER_HASH_MISMATCH": "LEDGER_MISMATCH",
    "PACKET_HASH_MISMATCH": "LEDGER_MISMATCH",
    "RUN_ID_MISMATCH": "LEDGER_MISMATCH",
}


def _backend_root() -> Path:
    """Resolve the backend root regardless of the current working directory."""

    return Path(__file__).resolve().parents[2]


def _workflows_dir() -> Path:
    """Resolve the workflows directory for API metadata endpoints."""

    return _backend_root() / "workflows"


def get_state(request: Request) -> InMemoryApiState:
    """Return the shared demo state from the FastAPI app object."""

    state = getattr(request.app.state, "tosco_state", None)
    if not isinstance(state, InMemoryApiState):
        raise ApiRouteError(
            500,
            "STATE_NOT_INITIALIZED",
            "The backend demo state is not initialized.",
        )
    return state


def _workflow_metadata(workflow: Any) -> dict[str, Any]:
    """Serialize only the workflow fields the current frontend needs."""

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

    raise ApiRouteError(exc.status_code, exc.error_code, exc.message) from exc


def _load_clearance_token(raw_token: str) -> ClearanceToken:
    """Parse a contract token string into the existing token model."""

    try:
        payload = json.loads(raw_token)
    except json.JSONDecodeError as exc:
        raise ApiRouteError(
            400,
            "MALFORMED_TOKEN",
            "The execution request token was not valid JSON.",
        ) from exc

    if not isinstance(payload, dict):
        raise ApiRouteError(
            400,
            "MALFORMED_TOKEN",
            "The execution request token must decode to a JSON object.",
        )

    decision_value = payload.get("decision")
    if isinstance(decision_value, str) and decision_value.strip() and decision_value != Decision.ALLOW.value:
        raise ApiRouteError(
            400,
            "NON_ALLOW_TOKEN",
            "The execution request token did not authorize ALLOW.",
        )

    try:
        return ClearanceToken.model_validate(payload)
    except ValidationError as exc:
        raise ApiRouteError(
            400,
            "MALFORMED_TOKEN",
            "The execution request token failed validation.",
        ) from exc


def _map_execution_reason(reason_code: str) -> str:
    """Translate engine-internal reason codes into the public contract vocabulary."""

    return _EXECUTION_REASON_MAP.get(reason_code, "TAMPERED_TOKEN")


@router.get("/health")
def health(state: InMemoryApiState = Depends(get_state)) -> dict[str, Any]:
    """Report a health payload plus current fallback configuration."""

    settings = load_settings_from_env()
    latest_run = state.latest_run()
    fallback_mode = latest_run.fallback_mode if latest_run is not None else not bool(settings.vultr_api_key)
    return {
        "status": "ok",
        "service": "TOSCO",
        "version": "0.1.0",
        "mode": "demo",
        "fallback_mode": fallback_mode,
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


@router.get("/workflows/{workflow_id}")
def get_workflow_definition(workflow_id: str) -> dict[str, object]:
    """Return the full parsed workflow definition for one workflow_id."""

    try:
        registry = load_workflow_registry(_workflows_dir())
        workflow = get_workflow(registry, workflow_id)
    except WorkflowLoadError as exc:
        raise ApiRouteError(
            404,
            "WORKFLOW_NOT_FOUND",
            f"Workflow '{workflow_id}' was not found.",
        ) from exc

    return workflow_to_contract_payload(workflow)


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


@router.post("/agent/propose", response_model=AgentProposeResponse)
def propose_agent_intent(
    payload: dict[str, Any] = Body(...),
    state: InMemoryApiState = Depends(get_state),
) -> AgentProposeResponse:
    """Accept a proposal request, build the intent from the seed, and do not decide."""

    try:
        request_payload = AgentProposeRequest.model_validate(payload)
    except ValidationError as exc:
        raise ApiRouteError(
            422,
            "INVALID_INTENT",
            "The proposal request body was invalid.",
        ) from exc

    try:
        seed = load_scenario_seed(request_payload.scenario)
    except ScenarioLoadError as exc:
        raise ApiRouteError(
            422,
            "INVALID_INTENT",
            "The proposal scenario was invalid.",
        ) from exc

    proposal = ReferenceAPAgent().propose_from_seed(seed)
    expected_intent = proposal.intent

    if request_payload.agent_id != expected_intent.agent_id:
        raise ApiRouteError(422, "INVALID_INTENT", "The proposal agent_id did not match the seeded scenario.")
    if request_payload.workflow != expected_intent.workflow:
        raise ApiRouteError(422, "INVALID_INTENT", "The proposal workflow did not match the seeded scenario.")
    if request_payload.action.model_dump(mode="json") != expected_intent.action.model_dump(mode="json"):
        raise ApiRouteError(422, "INVALID_INTENT", "The proposal action did not match the seeded scenario.")
    if list(request_payload.evidence_refs) != list(expected_intent.evidence_refs):
        raise ApiRouteError(422, "INVALID_INTENT", "The proposal evidence_refs did not match the seeded scenario.")
    if request_payload.requested_mode != expected_intent.requested_mode:
        raise ApiRouteError(422, "INVALID_INTENT", "The proposal requested_mode did not match the seeded scenario.")
    if request_payload.declared_confidence != expected_intent.declared_confidence:
        raise ApiRouteError(
            422,
            "INVALID_INTENT",
            "The proposal declared_confidence did not match the seeded scenario.",
        )

    state.register_proposal(expected_intent)
    return AgentProposeResponse(intent_id=expected_intent.intent_id, accepted=True)


@router.post("/runs/start")
async def start_run(
    payload: StartRunRequest,
    state: InMemoryApiState = Depends(get_state),
    response_format: str | None = Query(default=None, alias="format"),
) -> RunHandleResponse | RunSummaryResponse:
    """Start one scenario run using the shared ledger."""

    try:
        record = await state.start_run(payload.scenario, use_vultr=payload.use_vultr)
    except ApiStateError as exc:
        _raise_state_error(exc)

    if response_format == "summary":
        try:
            completed = await state.wait_for_completion(record.run_id)
        except ApiStateError as exc:
            _raise_state_error(exc)
        if completed.orchestrated_run is None:
            raise ApiRouteError(409, "RUN_NOT_READY", f"Run '{record.run_id}' is still processing.")
        return run_to_summary(completed.orchestrated_run)

    return RunHandleResponse(run_id=record.run_id)


@router.post("/runs/custom")
async def start_custom_run(
    payload: CustomRunRequest,
    state: InMemoryApiState = Depends(get_state),
    response_format: str | None = Query(default=None, alias="format"),
) -> RunHandleResponse | RunSummaryResponse:
    """Start one judge-supplied payment through the full clearance pipeline."""

    try:
        record = await state.start_custom_run(payload)
    except ApiStateError as exc:
        _raise_state_error(exc)

    if response_format == "summary":
        try:
            completed = await state.wait_for_completion(record.run_id)
        except ApiStateError as exc:
            _raise_state_error(exc)
        if completed.orchestrated_run is None:
            raise ApiRouteError(409, "RUN_NOT_READY", f"Run '{record.run_id}' is still processing.")
        return run_to_summary(completed.orchestrated_run)

    return RunHandleResponse(run_id=record.run_id)


@router.get("/integrations/vultr/status", response_model=VultrStatusResponse)
def get_vultr_status() -> VultrStatusResponse:
    """Expose safe Vultr configuration status without leaking the API key."""

    settings = load_settings_from_env()
    key_present = settings.vultr_api_key is not None and bool(settings.vultr_api_key.strip())
    return VultrStatusResponse(
        configured=key_present,
        base_url=settings.vultr_inference_base_url,
        model=settings.vultr_chat_model,
        mode="serverless-inference",
        key_present=key_present,
    )


@router.get("/runs", response_model=list[RunSummaryResponse])
async def list_runs(state: InMemoryApiState = Depends(get_state)) -> list[RunSummaryResponse]:
    """Return summaries for all completed demo runs."""

    responses: list[RunSummaryResponse] = []
    for record in state.list_runs():
        if record.orchestrated_run is None:
            continue
        responses.append(run_to_summary(record.orchestrated_run))
    return responses


@router.get("/runs/{run_id}")
async def get_run(
    run_id: str,
    state: InMemoryApiState = Depends(get_state),
    response_format: str | None = Query(default=None, alias="format"),
) -> RunSnapshotResponse | RunSummaryResponse:
    """Return either the contract snapshot or the legacy summary for one run."""

    try:
        if response_format == "summary":
            record = await state.wait_for_completion(run_id)
            if record.orchestrated_run is None:
                raise ApiRouteError(409, "RUN_NOT_READY", f"Run '{run_id}' is still processing.")
            return run_to_summary(record.orchestrated_run)

        snapshot = state.build_run_snapshot(run_id)
    except ApiStateError as exc:
        _raise_state_error(exc)

    return RunSnapshotResponse.model_validate(snapshot)


@router.get("/runs/{run_id}/events", response_model=None)
async def get_run_events(
    run_id: str,
    request: Request,
    state: InMemoryApiState = Depends(get_state),
    response_format: str | None = Query(default=None, alias="format"),
) -> Any:
    """Return either the legacy JSON timeline or the contract SSE stream."""

    if response_format == "json":
        try:
            record = await state.wait_for_completion(run_id)
        except ApiStateError as exc:
            _raise_state_error(exc)
        if record.orchestrated_run is None:
            raise ApiRouteError(409, "RUN_NOT_READY", f"Run '{run_id}' is still processing.")
        return EventTimelineResponse(
            run_id=record.run_id,
            events=list(record.orchestrated_run.timeline.events),
        )

    try:
        state.get_run(run_id)
    except ApiStateError as exc:
        _raise_state_error(exc)

    async def event_stream() -> Any:
        async for message in state.subscribe_contract_events(run_id):
            if await request.is_disconnected():
                break
            yield message.to_sse_bytes()

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/runs/{run_id}/proof", response_model=ProofPacketResponse)
async def get_run_proof(
    run_id: str,
    state: InMemoryApiState = Depends(get_state),
) -> ProofPacketResponse:
    """Return the sealed proof packet for one stored run."""

    try:
        record = await state.wait_for_completion(run_id)
    except ApiStateError as exc:
        _raise_state_error(exc)

    if record.orchestrated_run is None:
        raise ApiRouteError(409, "PROOF_NOT_READY", f"Run '{run_id}' has not sealed proof yet.")

    return ProofPacketResponse(
        run_id=record.run_id,
        proof_packet=record.orchestrated_run.proof_packet,
        proof_hash=record.orchestrated_run.proof_packet.proof_hash(),
        ledger_entry_hash=record.orchestrated_run.ledger_entry.entry_hash,
    )


@router.get("/runs/{run_id}/verify", response_model=VerifyRunResponse)
async def verify_run(
    run_id: str,
    state: InMemoryApiState = Depends(get_state),
) -> VerifyRunResponse:
    """Live-verify one run's proof against the shared ledger."""

    try:
        await state.wait_for_completion(run_id)
        verification = state.verify_run(run_id)
    except ApiStateError as exc:
        _raise_state_error(exc)

    return VerifyRunResponse.model_validate(verification)


@router.post("/runs/{run_id}/tamper-demo", response_model=VerifyRunResponse)
async def tamper_run(
    run_id: str,
    state: InMemoryApiState = Depends(get_state),
) -> VerifyRunResponse:
    """Mutate one ledger row for the demo and return the failed verification state."""

    try:
        await state.wait_for_completion(run_id)
        verification = state.tamper_run(run_id)
    except ApiStateError as exc:
        _raise_state_error(exc)

    return VerifyRunResponse.model_validate(verification)


@router.post("/execution/attempt", response_model=ExecutionAttemptResponse)
async def attempt_execution(
    payload: ExecutionAttemptRequest,
    state: InMemoryApiState = Depends(get_state),
) -> ExecutionAttemptResponse:
    """Call the existing mock bank adapter through the public control-plane contract."""

    try:
        record = await state.wait_for_completion(payload.run_id)
    except ApiStateError as exc:
        _raise_state_error(exc)

    if record.orchestrated_run is None:
        raise ApiRouteError(409, "RUN_NOT_READY", f"Run '{payload.run_id}' is still processing.")

    token = None
    if payload.token is not None:
        token = _load_clearance_token(payload.token)

    payment_request = build_payment_request_from_context(
        record.orchestrated_run.run_context,
        token,
    ).model_copy(
        update={
            "vendor_id": payload.vendor_id,
            "amount": payload.amount,
        }
    )

    result = attempt_mock_bank_execution(
        payment_request,
        token=token,
        secret=OrchestratorConfig().token_secret,
        now=OrchestratorConfig().now,
        expected_packet_hash=record.orchestrated_run.proof_packet.proof_hash(),
        expected_ledger_entry_hash=record.orchestrated_run.ledger_entry.entry_hash,
    )
    return ExecutionAttemptResponse(
        executed=result.accepted,
        reason="CLEARED" if result.accepted else _map_execution_reason(result.reason_code),
    )


@router.post("/reset")
def reset_demo(state: InMemoryApiState = Depends(get_state)) -> dict[str, Any]:
    """Reset runs and the shared ledger to a fresh demo state."""

    state.reset()
    return {
        "status": "reset",
        "runs": 0,
    }
