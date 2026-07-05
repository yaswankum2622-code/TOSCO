from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest


BACKEND_ROOT = Path(__file__).resolve().parents[1]


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture()
def live_server() -> str:
    port = _free_port()
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "app.api.app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=str(BACKEND_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base_url = f"http://127.0.0.1:{port}"

    client = httpx.Client(base_url=base_url, timeout=5.0)
    try:
        for _ in range(50):
            try:
                response = client.get("/api/health")
                if response.status_code == 200:
                    break
            except httpx.HTTPError:
                time.sleep(0.1)
        else:
            raise AssertionError("Live uvicorn server did not start in time")

        yield base_url
    finally:
        client.close()
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)


def _reset(client: httpx.Client) -> None:
    response = client.post("/api/reset")
    assert response.status_code == 200


def _wait_for_snapshot(
    client: httpx.Client,
    run_id: str,
    *,
    timeout_seconds: float = 10.0,
) -> dict[str, object]:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        response = client.get(f"/api/runs/{run_id}")
        assert response.status_code == 200
        snapshot = response.json()
        if snapshot["status"] == "COMPLETED":
            return snapshot
        time.sleep(0.05)

    raise AssertionError(f"Run '{run_id}' did not complete in time")


def _tampered_token(raw_token: str) -> str:
    payload = json.loads(raw_token)
    payload["signature"] = "0" * len(payload["signature"])
    return json.dumps(payload, separators=(",", ":"))


def _sse_events(client: httpx.Client, run_id: str) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    with client.stream("GET", f"/api/runs/{run_id}/events") as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        for line in response.iter_lines():
            if not line:
                continue
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


def test_workflow_detail_contract(live_server: str) -> None:
    client = httpx.Client(base_url=live_server, timeout=10.0)
    try:
        response = client.get("/api/workflows/vendor_payment")
        assert response.status_code == 200
        payload = response.json()
        assert payload["workflow_id"] == "vendor_payment"
        assert payload["workflow_name"] == "AI Vendor Payment & Bank-Change Clearance"
        assert payload["required_evidence_types"] == [
            "invoice",
            "po",
            "grn",
            "vendor_master",
            "policy_pack",
        ]
    finally:
        client.close()


def test_public_contract_live_flow(live_server: str) -> None:
    client = httpx.Client(base_url=live_server, timeout=10.0)
    try:
        _reset(client)

        propose_response = client.post(
            "/api/agent/propose",
            json={
                "agent_id": "reference-ap-agent",
                "workflow": "vendor_payment",
                "action": {
                    "type": "payment",
                    "vendor_id": "VEND-ACME-001",
                    "amount": 340000,
                    "currency": "USD",
                    "bank_account_last4": "7730",
                },
                "evidence_refs": [
                    "grn-forgery-2091",
                    "invoice-forgery-7730",
                    "po-forgery-2091",
                    "policy-pack-v1",
                    "vendor-master-acme-updated",
                ],
                "declared_confidence": 0.94,
                "requested_mode": "assisted",
                "scenario": "forgery",
            },
        )
        assert propose_response.status_code == 200
        assert propose_response.json() == {
            "intent_id": "intent-forgery-001",
            "accepted": True,
        }

        start_forgery = client.post("/api/runs/start", json={"scenario": "forgery"})
        assert start_forgery.status_code == 200
        forgery_run_id = start_forgery.json()["run_id"]

        events = _sse_events(client, forgery_run_id)
        event_names = [event["event"] for event in events]
        assert event_names[0] == "PLAN_STARTED"
        assert event_names[-1] == "EXECUTION_ATTEMPTED"
        assert event_names.count("EVIDENCE_RETRIEVED") == 5
        assert event_names.count("GATE_STARTED") == 5
        assert event_names.count("GATE_COMPLETED") == 5
        assert "TOKEN_ISSUED" not in event_names

        forgery_execute = client.post(
            "/api/execution/attempt",
            json={
                "run_id": forgery_run_id,
                "token": None,
                "vendor_id": "VEND-ACME-001",
                "amount": 340000,
            },
        )
        assert forgery_execute.status_code == 200
        assert forgery_execute.json() == {"executed": False, "reason": "NO_TOKEN"}

        _reset(client)
        start_injection = client.post("/api/runs/start", json={"scenario": "injection"})
        assert start_injection.status_code == 200
        injection_run_id = start_injection.json()["run_id"]
        injection_execute = client.post(
            "/api/execution/attempt",
            json={
                "run_id": injection_run_id,
                "token": None,
                "vendor_id": "VEND-ACME-001",
                "amount": 340000,
            },
        )
        assert injection_execute.status_code == 200
        assert injection_execute.json() == {"executed": False, "reason": "NO_TOKEN"}

        _reset(client)
        start_clean = client.post("/api/runs/start", json={"scenario": "clean"})
        assert start_clean.status_code == 200
        clean_run_id = start_clean.json()["run_id"]
        clean_snapshot = _wait_for_snapshot(client, clean_run_id)
        token = clean_snapshot["clearance_token"]
        assert isinstance(token, str) and token

        clean_execute = client.post(
            "/api/execution/attempt",
            json={
                "run_id": clean_run_id,
                "token": token,
                "vendor_id": "VEND-ACME-001",
                "amount": 340000,
            },
        )
        assert clean_execute.status_code == 200
        assert clean_execute.json() == {"executed": True, "reason": "CLEARED"}

        clean_no_token = client.post(
            "/api/execution/attempt",
            json={
                "run_id": clean_run_id,
                "token": None,
                "vendor_id": "VEND-ACME-001",
                "amount": 340000,
            },
        )
        assert clean_no_token.status_code == 200
        assert clean_no_token.json() == {"executed": False, "reason": "NO_TOKEN"}

        tampered_token_response = client.post(
            "/api/execution/attempt",
            json={
                "run_id": clean_run_id,
                "token": _tampered_token(token),
                "vendor_id": "VEND-ACME-001",
                "amount": 340000,
            },
        )
        assert tampered_token_response.status_code == 200
        assert tampered_token_response.json() == {
            "executed": False,
            "reason": "TAMPERED_TOKEN",
        }

        amount_mismatch = client.post(
            "/api/execution/attempt",
            json={
                "run_id": clean_run_id,
                "token": token,
                "vendor_id": "VEND-ACME-001",
                "amount": 340001,
            },
        )
        assert amount_mismatch.status_code == 200
        assert amount_mismatch.json() == {
            "executed": False,
            "reason": "AMOUNT_MISMATCH",
        }

        vendor_mismatch = client.post(
            "/api/execution/attempt",
            json={
                "run_id": clean_run_id,
                "token": token,
                "vendor_id": "VEND-OTHER-999",
                "amount": 340000,
            },
        )
        assert vendor_mismatch.status_code == 200
        assert vendor_mismatch.json() == {
            "executed": False,
            "reason": "VENDOR_MISMATCH",
        }
    finally:
        client.close()
