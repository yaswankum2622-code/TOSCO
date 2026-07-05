from __future__ import annotations

from fastapi.testclient import TestClient

from app.api.app import create_app


def make_client() -> TestClient:
    return TestClient(create_app())


def start_run(client: TestClient, scenario: str) -> dict:
    response = client.post("/api/runs/start?format=summary", json={"scenario": scenario})
    assert response.status_code == 200
    return response.json()


def get_gate_completed_reason(events: list[dict], gate_id: str) -> str:
    for event in events:
        if event["event_type"] == "GATE_COMPLETED" and event["payload"].get("gate_id") == gate_id:
            return event["payload"]["reason_code"]
    raise AssertionError(f"Missing GATE_COMPLETED event for {gate_id}")


def test_health_route_works() -> None:
    with make_client() as client:
        response = client.get("/api/health")

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "TOSCO"
    assert "fallback_mode" in payload


def test_workflows_route_works() -> None:
    with make_client() as client:
        response = client.get("/api/workflows")

    assert response.status_code == 200
    payload = response.json()
    assert any(workflow["workflow_id"] == "vendor_payment" for workflow in payload)
    vendor_payment = next(workflow for workflow in payload if workflow["workflow_id"] == "vendor_payment")
    assert "G1_EVIDENCE" in vendor_payment["gates_to_run"]


def test_scenarios_route_works() -> None:
    with make_client() as client:
        response = client.get("/api/scenarios")

    assert response.status_code == 200
    scenarios = [item["scenario"] for item in response.json()]
    assert scenarios == ["clean", "injection", "forgery"]


def test_start_clean_run() -> None:
    with make_client() as client:
        payload = start_run(client, "clean")

    assert payload["final_decision"] == "ALLOW"
    assert payload["allow_execution"] is True
    assert payload["token_issued"] is True
    assert payload["mock_bank_status"] == "ACCEPTED"


def test_start_injection_run() -> None:
    with make_client() as client:
        payload = start_run(client, "injection")

    assert payload["final_decision"] == "BLOCK"
    assert payload["allow_execution"] is False
    assert payload["token_issued"] is False
    assert payload["mock_bank_status"] == "REJECTED"


def test_start_forgery_run() -> None:
    with make_client() as client:
        payload = start_run(client, "forgery")

    assert payload["final_decision"] == "FREEZE"
    assert payload["allow_execution"] is False
    assert payload["token_issued"] is False
    assert payload["mock_bank_status"] == "REJECTED"


def test_get_run_summary() -> None:
    with make_client() as client:
        started = start_run(client, "clean")
        response = client.get(f"/api/runs/{started['run_id']}?format=summary")

    assert response.status_code == 200
    payload = response.json()
    assert payload["run_id"] == started["run_id"]
    assert payload["final_decision"] == "ALLOW"


def test_get_run_events() -> None:
    with make_client() as client:
        started = start_run(client, "clean")
        response = client.get(f"/api/runs/{started['run_id']}/events?format=json")

    assert response.status_code == 200
    payload = response.json()
    assert payload["events"]
    event_types = [event["event_type"] for event in payload["events"]]
    assert "AGENT_PROPOSED" in event_types
    assert "DECISION_MADE" in event_types
    assert "PROOF_SEALED" in event_types
    assert "EXECUTION_ACCEPTED" in event_types


def test_get_run_proof() -> None:
    with make_client() as client:
        started = start_run(client, "clean")
        response = client.get(f"/api/runs/{started['run_id']}/proof")

    assert response.status_code == 200
    assert len(response.json()["proof_hash"]) == 64
    assert len(response.json()["ledger_entry_hash"]) == 64
    assert "invoice body text" not in response.text.lower()
    assert "IGNORE PREVIOUS INSTRUCTIONS" not in response.text


def test_verify_before_tamper() -> None:
    with make_client() as client:
        started = start_run(client, "clean")
        response = client.get(f"/api/runs/{started['run_id']}/verify")

    assert response.status_code == 200
    payload = response.json()
    assert payload["verified"] is True
    assert payload["ledger_chain_valid"] is True
    assert payload["packet_entry_valid"] is True
    assert payload["chain_head"]


def test_tamper_demo_breaks_verification() -> None:
    with make_client() as client:
        started = start_run(client, "clean")
        verified_before = client.get(f"/api/runs/{started['run_id']}/verify")
        tampered = client.post(f"/api/runs/{started['run_id']}/tamper-demo")
        verified_after = client.get(f"/api/runs/{started['run_id']}/verify")

    assert verified_before.status_code == 200
    assert verified_before.json()["verified"] is True
    assert tampered.status_code == 200
    assert tampered.json()["verified"] is False
    assert tampered.json()["tampered_field"] == "packet_hash"
    assert tampered.json()["verify_now"] is False
    assert verified_after.status_code == 200
    assert verified_after.json()["verified"] is False


def test_missing_run_returns_404() -> None:
    with make_client() as client:
        response = client.get("/api/runs/not-found?format=summary")

    assert response.status_code == 404
    assert response.json()["error"] == "RUN_NOT_FOUND"
    assert response.json()["error_code"] == "RUN_NOT_FOUND"


def test_invalid_scenario_returns_400() -> None:
    with make_client() as client:
        response = client.post("/api/runs/start", json={"scenario": "unknown"})

    assert response.status_code == 400
    assert response.json()["error"] == "INVALID_SCENARIO"
    assert response.json()["error_code"] == "INVALID_SCENARIO"


def test_reset_clears_runs() -> None:
    with make_client() as client:
        start_run(client, "clean")
        runs_before = client.get("/api/runs")
        reset = client.post("/api/reset")
        runs_after = client.get("/api/runs")

    assert runs_before.status_code == 200
    assert len(runs_before.json()) == 1
    assert reset.status_code == 200
    assert reset.json() == {"status": "reset", "runs": 0}
    assert runs_after.status_code == 200
    assert runs_after.json() == []


def test_multiple_runs_share_ledger_chain() -> None:
    with make_client() as client:
        client.post("/api/reset")
        clean = start_run(client, "clean")
        injection = start_run(client, "injection")
        forgery = start_run(client, "forgery")
        clean_verify = client.get(f"/api/runs/{clean['run_id']}/verify")
        injection_verify = client.get(f"/api/runs/{injection['run_id']}/verify")
        forgery_verify = client.get(f"/api/runs/{forgery['run_id']}/verify")

    assert clean_verify.json()["verified"] is True
    assert injection_verify.json()["verified"] is True
    assert forgery_verify.json()["verified"] is True


def test_api_exposes_computed_gate_reasons() -> None:
    with make_client() as client:
        injection = start_run(client, "injection")
        forgery = start_run(client, "forgery")
        injection_events = client.get(f"/api/runs/{injection['run_id']}/events?format=json")
        forgery_events = client.get(f"/api/runs/{forgery['run_id']}/events?format=json")

    assert injection_events.status_code == 200
    assert forgery_events.status_code == 200
    assert (
        get_gate_completed_reason(injection_events.json()["events"], "G2_GROUNDEDNESS")
        == "BANK_ACCOUNT_MISMATCH"
    )
    assert (
        get_gate_completed_reason(forgery_events.json()["events"], "G5_REALITY")
        == "REALITY_OWNER_MISMATCH_FREEZE"
    )
