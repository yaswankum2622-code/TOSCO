from __future__ import annotations

import time

from fastapi.testclient import TestClient

from app.api.app import create_app


def make_client() -> TestClient:
    return TestClient(create_app())


def start_custom_run(client: TestClient, payload: dict) -> dict:
    response = client.post("/api/runs/custom?format=summary", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def wait_for_run_status(client: TestClient, run_id: str, expected_status: str) -> dict:
    for _ in range(100):
        snapshot = client.get(f"/api/runs/{run_id}").json()
        if snapshot["status"] == expected_status:
            return snapshot
        time.sleep(0.05)
    raise AssertionError(f"Run '{run_id}' never reached status '{expected_status}'.")


def clean_custom_payload(**overrides: object) -> dict:
    payload = {
        "vendor_id": "VEND-ACME-001",
        "amount": 340000,
        "currency": "USD",
        "bank_account_last4": "8821",
        "registered_bank_last4": "8821",
        "invoice_text": "Invoice for industrial supplies. Pay registered account ending 8821.",
        "bank_owner_matches_vendor": True,
        "request_domain_age_days": 2200,
        "logistics_confirmed": True,
        "is_first_payment_to_account": False,
        "use_vultr": False,
    }
    payload.update(overrides)
    return payload


def test_escalate_custom_run_pauses_for_review() -> None:
    with make_client() as client:
        started = client.post(
            "/api/runs/custom",
            json=clean_custom_payload(is_first_payment_to_account=True),
        ).json()
        run_id = started["run_id"]
        snapshot = wait_for_run_status(client, run_id, "AWAITING_REVIEW")

    assert snapshot["status"] == "AWAITING_REVIEW"
    assert snapshot["decision"] == "ESCALATE"
    assert snapshot["review_reason"] is not None
    assert snapshot["clearance_token"] is None


def test_review_approve_issues_token_and_records_reviewer() -> None:
    with make_client() as client:
        started = client.post(
            "/api/runs/custom",
            json=clean_custom_payload(is_first_payment_to_account=True),
        ).json()
        run_id = started["run_id"]
        wait_for_run_status(client, run_id, "AWAITING_REVIEW")
        review = client.post(
            f"/api/runs/{run_id}/review?format=summary",
            json={"reviewer_id": "judge-001", "action": "APPROVED"},
        )

        assert review.status_code == 200, review.text
        payload = review.json()
        assert payload["final_decision"] == "ALLOW"
        assert payload["token_issued"] is True
        assert payload["mock_bank_status"] == "ACCEPTED"

        proof = client.get(f"/api/runs/{run_id}/proof").json()

    assert proof["proof_packet"]["human_review"]["reviewer_id"] == "judge-001"
    assert proof["proof_packet"]["human_review"]["action"] == "APPROVED"


def test_review_reject_blocks_without_token() -> None:
    with make_client() as client:
        started = client.post(
            "/api/runs/custom",
            json=clean_custom_payload(is_first_payment_to_account=True),
        ).json()
        run_id = started["run_id"]
        wait_for_run_status(client, run_id, "AWAITING_REVIEW")
        review = client.post(
            f"/api/runs/{run_id}/review?format=summary",
            json={"reviewer_id": "judge-002", "action": "REJECTED"},
        )

    assert review.status_code == 200, review.text
    payload = review.json()
    assert payload["final_decision"] == "BLOCK"
    assert payload["token_issued"] is False
    assert payload["mock_bank_status"] == "REJECTED"


def test_clean_custom_allow_skips_review() -> None:
    with make_client() as client:
        started = start_custom_run(client, clean_custom_payload())
        run_id = started["run_id"]
        snapshot = wait_for_run_status(client, run_id, "COMPLETED")

    assert snapshot["status"] == "COMPLETED"
    assert snapshot["decision"] == "ALLOW"
    assert snapshot["clearance_token"] is not None
