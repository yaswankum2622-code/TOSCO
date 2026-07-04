from __future__ import annotations

import json

import httpx
import pytest

from app.integrations.vultr import (
    VultrInferenceClient,
    VultrIntegrationError,
    VultrSettings,
    extract_json_object,
)


def test_vultr_settings_configured_false_without_key() -> None:
    settings = VultrSettings(api_key=None)

    assert settings.configured is False


def test_chat_completion_returns_fallback_when_not_configured() -> None:
    client = VultrInferenceClient(VultrSettings(api_key=None))

    result = client.chat_completion(system_prompt="Return JSON.", user_prompt='{"status":"ok"}')

    assert result.ok is False
    assert result.error_code == "VULTR_NOT_CONFIGURED"
    assert result.fallback_used is True


def test_extract_json_object_parses_plain_json() -> None:
    payload = extract_json_object('{"status":"ok"}')

    assert payload == {"status": "ok"}


def test_extract_json_object_parses_fenced_json() -> None:
    payload = extract_json_object('```json\n{"status":"ok"}\n```')

    assert payload == {"status": "ok"}


def test_extract_json_object_rejects_invalid_json() -> None:
    with pytest.raises(VultrIntegrationError):
        extract_json_object("not-json")


def test_chat_completion_sends_correct_request_shape_with_mocked_httpx() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["authorization"] = request.headers["Authorization"]
        captured["content_type"] = request.headers["Content-Type"]
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": '{"status":"ok"}',
                        }
                    }
                ],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 4,
                    "total_tokens": 16,
                },
            },
        )

    transport = httpx.MockTransport(handler)
    settings = VultrSettings(
        api_key="test-vultr-key",
        base_url="https://api.vultrinference.com/v1",
        chat_model="nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16",
    )
    with httpx.Client(transport=transport, timeout=5.0) as http_client:
        client = VultrInferenceClient(settings, http_client=http_client)
        result = client.chat_completion(
            system_prompt="Return JSON.",
            user_prompt='{"status":"ok"}',
        )

    assert result.ok is True
    assert result.content == '{"status":"ok"}'
    assert result.usage is not None
    assert result.usage.total_tokens == 16
    assert captured["path"] == "/v1/chat/completions"
    assert str(captured["authorization"]).startswith("Bearer ")
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == settings.chat_model
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][1]["role"] == "user"


def test_extract_vendor_payment_fields_returns_typed_fields_from_mocked_response() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "fields": {
                                        "invoice_id": "INV-1",
                                        "vendor_name": "ACME",
                                        "amount": 340000,
                                        "bank_account_last4": "8821",
                                    },
                                    "source_spans": {
                                        "invoice_id": [1],
                                        "vendor_name": [1],
                                        "amount": [1],
                                        "bank_account_last4": [1],
                                    },
                                }
                            )
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    settings = VultrSettings(api_key="test-vultr-key")
    with httpx.Client(transport=transport, timeout=5.0) as http_client:
        client = VultrInferenceClient(settings, http_client=http_client)
        result = client.extract_vendor_payment_fields(
            evidence={"invoice": {"doc_id": "invoice-1"}},
            required_fields=["invoice_id", "vendor_name", "amount", "bank_account_last4"],
        )

    dumped = result.model_dump(mode="json")
    assert result.ok is True
    assert result.fields["bank_account_last4"] == "8821"
    assert result.raw_content_hash is not None
    assert "content" not in dumped


def test_invalid_extraction_json_returns_ok_false() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "not valid json",
                        }
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, timeout=5.0) as http_client:
        client = VultrInferenceClient(
            VultrSettings(api_key="test-vultr-key"),
            http_client=http_client,
        )
        result = client.extract_vendor_payment_fields(
            evidence={"invoice": {"doc_id": "invoice-1"}},
            required_fields=["invoice_id"],
        )

    assert result.ok is False
    assert result.error_code == "VULTR_JSON_PARSE_ERROR"


def test_vultr_settings_do_not_expose_api_key_in_repr_or_model_dump() -> None:
    settings = VultrSettings(api_key="super-secret-test-key")

    assert "super-secret-test-key" not in repr(settings)
    assert "super-secret-test-key" not in json.dumps(settings.model_dump(mode="json"))
