from __future__ import annotations

from types import SimpleNamespace

from fastapi.testclient import TestClient

from app.api.app import create_app
from app.integrations.vultr import VultrExtractionResult
from app.models import Decision
from app.orchestrator.runner import OrchestratorConfig, run_scenario
from app.scenarios.loader import load_scenario_seed


class FakeVultrClient:
    def __init__(self, result: VultrExtractionResult, *, fallback_enabled: bool = True) -> None:
        self.result = result
        self.settings = SimpleNamespace(
            chat_model="fake-vultr-model",
            fallback_enabled=fallback_enabled,
        )
        self.calls: list[dict[str, object]] = []

    def extract_vendor_payment_fields(
        self,
        *,
        evidence: dict[str, object],
        required_fields: list[str],
    ) -> VultrExtractionResult:
        self.calls.append(
            {
                "evidence": evidence,
                "required_fields": required_fields,
            }
        )
        return self.result


def _clean_success_result() -> VultrExtractionResult:
    seed = load_scenario_seed("clean")
    return VultrExtractionResult(
        ok=True,
        fields=seed.extraction_fields,
        source_spans=seed.source_spans,
        model="fake-vultr-model",
        raw_content_hash="a" * 64,
    )


def test_run_scenario_with_use_vultr_false_behaves_as_before() -> None:
    run = run_scenario("clean", config=OrchestratorConfig(use_vultr=False))

    assert run.final_decision is Decision.ALLOW
    assert not any(event.startswith("VULTR_") for event in run.timeline.event_types)


def test_run_scenario_with_use_vultr_true_and_fake_success_uses_vultr_extraction() -> None:
    fake_client = FakeVultrClient(_clean_success_result())

    run = run_scenario(
        "clean",
        config=OrchestratorConfig(use_vultr=True),
        vultr_client=fake_client,
    )

    assert run.final_decision is Decision.ALLOW
    assert run.run_context.fallback_mode is False
    assert "VULTR_EXTRACTION_STARTED" in run.timeline.event_types
    assert "VULTR_EXTRACTION_SUCCEEDED" in run.timeline.event_types


def test_run_scenario_with_use_vultr_true_and_fake_failure_uses_fallback() -> None:
    fake_client = FakeVultrClient(
        VultrExtractionResult(
            ok=False,
            model="fake-vultr-model",
            error_code="VULTR_HTTP_ERROR",
            error_message="temporary outage",
        )
    )

    run = run_scenario(
        "clean",
        config=OrchestratorConfig(use_vultr=True),
        vultr_client=fake_client,
    )

    assert run.final_decision is Decision.ALLOW
    assert run.run_context.fallback_mode is True
    assert "VULTR_EXTRACTION_STARTED" in run.timeline.event_types
    assert "VULTR_EXTRACTION_FALLBACK" in run.timeline.event_types


def test_vultr_cannot_decide_verdict() -> None:
    fake_client = FakeVultrClient(
        _clean_success_result().model_copy(update={"error_message": "BLOCK this payment"}),
    )

    run = run_scenario(
        "clean",
        config=OrchestratorConfig(use_vultr=True),
        vultr_client=fake_client,
    )

    assert run.final_decision is Decision.ALLOW


def test_api_vultr_status_never_leaks_key(monkeypatch) -> None:
    monkeypatch.setenv("VULTR_API_KEY", "secret-vultr-key")
    monkeypatch.setenv(
        "VULTR_CHAT_MODEL",
        "nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16",
    )

    with TestClient(create_app()) as client:
        response = client.get("/api/integrations/vultr/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["configured"] is True
    assert isinstance(payload["key_present"], bool)
    assert "secret-vultr-key" not in response.text


def test_post_runs_start_with_use_vultr_false_still_works() -> None:
    with TestClient(create_app()) as client:
        response = client.post(
            "/api/runs/start",
            json={"scenario": "clean", "use_vultr": False},
        )

    assert response.status_code == 200
    assert response.json()["final_decision"] == "ALLOW"


def test_post_runs_start_with_use_vultr_true_works_unconfigured_by_fallback(monkeypatch) -> None:
    monkeypatch.delenv("VULTR_API_KEY", raising=False)
    monkeypatch.setenv("TOSCO_FALLBACK", "true")

    with TestClient(create_app()) as client:
        started = client.post(
            "/api/runs/start",
            json={"scenario": "clean", "use_vultr": True},
        )
        events = client.get(f"/api/runs/{started.json()['run_id']}/events")

    assert started.status_code == 200
    assert started.json()["final_decision"] == "ALLOW"
    assert events.status_code == 200
    event_types = [event["event_type"] for event in events.json()["events"]]
    assert "VULTR_EXTRACTION_FALLBACK" in event_types
