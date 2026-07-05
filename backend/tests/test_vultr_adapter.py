from __future__ import annotations

import json

import httpx
import pytest

from app.integrations.vultr import (
    ExtractionNormalizationError,
    VultrInferenceClient,
    VultrIntegrationError,
    VultrSettings,
    extract_chat_content_from_response,
    extract_json_object,
    normalize_extraction_payload,
    summarize_response_shape,
)


def test_vultr_settings_configured_false_without_key() -> None:
    settings = VultrSettings(api_key=None)

    assert settings.configured is False


def test_vultr_settings_normalize_full_chat_completions_url() -> None:
    settings = VultrSettings(
        api_key="test-vultr-key",
        base_url="https://api.vultrinference.com/v1/chat/completions",
    )

    assert settings.base_url == "https://api.vultrinference.com/v1"


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


def test_extract_json_object_parses_text_before_and_after_json() -> None:
    payload = extract_json_object('Here is the JSON: {"status":"ok","provider":"vultr"} Thanks!')

    assert payload == {"status": "ok", "provider": "vultr"}


def test_extract_json_object_rejects_array_json() -> None:
    with pytest.raises(VultrIntegrationError, match="object"):
        extract_json_object('["not","an","object"]')


def test_extract_json_object_rejects_invalid_json() -> None:
    with pytest.raises(VultrIntegrationError):
        extract_json_object("not-json")


def test_normalize_extraction_payload_accepts_canonical_shape() -> None:
    fields, source_spans = normalize_extraction_payload(
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
        },
        required_fields=["invoice_id", "vendor_name", "amount", "bank_account_last4"],
    )

    assert fields["invoice_id"] == "INV-1"
    assert source_spans["bank_account_last4"] == [1]


def test_normalize_extraction_payload_accepts_flat_shape() -> None:
    fields, source_spans = normalize_extraction_payload(
        {
            "invoice_id": "INV-1",
            "vendor_name": "ACME",
            "amount": 340000,
            "bank_account_last4": "8821",
            "source_spans": {
                "invoice_id": [1],
                "vendor_name": [1],
                "amount": [1],
                "bank_account_last4": [1],
            },
        },
        required_fields=["invoice_id", "vendor_name", "amount", "bank_account_last4"],
    )

    assert fields["vendor_name"] == "ACME"
    assert source_spans["amount"] == [1]


def test_normalize_extraction_payload_accepts_extracted_fields_and_sources() -> None:
    fields, source_spans = normalize_extraction_payload(
        {
            "extracted_fields": {
                "invoice_id": "INV-1",
                "vendor_name": "ACME",
                "amount": 340000,
                "bank_account_last4": "8821",
            },
            "sources": {
                "invoice_id": [1],
                "vendor_name": [1],
                "amount": [1],
                "bank_account_last4": [1],
            },
        },
        required_fields=["invoice_id", "vendor_name", "amount", "bank_account_last4"],
    )

    assert fields["amount"] == 340000
    assert source_spans["invoice_id"] == [1]


def test_normalize_extraction_payload_accepts_nested_data_shape() -> None:
    fields, source_spans = normalize_extraction_payload(
        {
            "data": {
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
        },
        required_fields=["invoice_id", "vendor_name", "amount", "bank_account_last4"],
    )

    assert fields["bank_account_last4"] == "8821"
    assert source_spans["vendor_name"] == [1]


def test_normalize_extraction_payload_normalizes_numeric_bank_suffix() -> None:
    fields, _ = normalize_extraction_payload(
        {
            "fields": {
                "invoice_id": "INV-1",
                "vendor_name": "ACME",
                "amount": 340000,
                "bank_account_last4": 8821,
            },
            "source_spans": {
                "invoice_id": [1],
                "vendor_name": [1],
                "amount": [1],
                "bank_account_last4": [1],
            },
        },
        required_fields=["invoice_id", "vendor_name", "amount", "bank_account_last4"],
    )

    assert fields["bank_account_last4"] == "8821"


def test_normalize_extraction_payload_takes_last_four_digits() -> None:
    fields, _ = normalize_extraction_payload(
        {
            "fields": {
                "invoice_id": "INV-1",
                "vendor_name": "ACME",
                "amount": 340000,
                "bank_account_last4": "00008821",
            },
            "source_spans": {
                "invoice_id": [1],
                "vendor_name": [1],
                "amount": [1],
                "bank_account_last4": [1],
            },
        },
        required_fields=["invoice_id", "vendor_name", "amount", "bank_account_last4"],
    )

    assert fields["bank_account_last4"] == "8821"


def test_normalize_extraction_payload_normalizes_amount_string() -> None:
    fields, _ = normalize_extraction_payload(
        {
            "fields": {
                "invoice_id": "INV-1",
                "vendor_name": "ACME",
                "amount": "$340,000",
                "bank_account_last4": "8821",
            },
            "source_spans": {
                "invoice_id": [1],
                "vendor_name": [1],
                "amount": [1],
                "bank_account_last4": [1],
            },
        },
        required_fields=["invoice_id", "vendor_name", "amount", "bank_account_last4"],
    )

    assert fields["amount"] == 340000


def test_normalize_extraction_payload_normalizes_span_variants() -> None:
    _, source_spans = normalize_extraction_payload(
        {
            "fields": {
                "invoice_id": "INV-1",
                "vendor_name": "ACME",
                "amount": 340000,
                "bank_account_last4": "8821",
            },
            "source_spans": {
                "invoice_id": 1,
                "vendor_name": "1",
                "amount": ["1"],
                "bank_account_last4": [1],
            },
        },
        required_fields=["invoice_id", "vendor_name", "amount", "bank_account_last4"],
    )

    assert source_spans["invoice_id"] == [1]
    assert source_spans["vendor_name"] == [1]
    assert source_spans["amount"] == [1]


def test_normalize_extraction_payload_rejects_missing_required_field() -> None:
    with pytest.raises(ExtractionNormalizationError, match="invoice_id"):
        normalize_extraction_payload(
            {
                "fields": {
                    "vendor_name": "ACME",
                    "amount": 340000,
                    "bank_account_last4": "8821",
                },
                "source_spans": {
                    "vendor_name": [1],
                    "amount": [1],
                    "bank_account_last4": [1],
                },
            },
            required_fields=["invoice_id", "vendor_name", "amount", "bank_account_last4"],
        )


def test_normalize_extraction_payload_rejects_missing_source_span() -> None:
    with pytest.raises(ExtractionNormalizationError, match="source spans"):
        normalize_extraction_payload(
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
                },
            },
            required_fields=["invoice_id", "vendor_name", "amount", "bank_account_last4"],
        )


def test_normalize_extraction_payload_rejects_invalid_bank_suffix() -> None:
    with pytest.raises(ExtractionNormalizationError, match="bank_account_last4"):
        normalize_extraction_payload(
            {
                "fields": {
                    "invoice_id": "INV-1",
                    "vendor_name": "ACME",
                    "amount": 340000,
                    "bank_account_last4": "88",
                },
                "source_spans": {
                    "invoice_id": [1],
                    "vendor_name": [1],
                    "amount": [1],
                    "bank_account_last4": [1],
                },
            },
            required_fields=["invoice_id", "vendor_name", "amount", "bank_account_last4"],
        )


def test_normalize_extraction_payload_rejects_invalid_amount() -> None:
    with pytest.raises(ExtractionNormalizationError, match="amount"):
        normalize_extraction_payload(
            {
                "fields": {
                    "invoice_id": "INV-1",
                    "vendor_name": "ACME",
                    "amount": "not-a-number",
                    "bank_account_last4": "8821",
                },
                "source_spans": {
                    "invoice_id": [1],
                    "vendor_name": [1],
                    "amount": [1],
                    "bank_account_last4": [1],
                },
            },
            required_fields=["invoice_id", "vendor_name", "amount", "bank_account_last4"],
        )


def test_extract_chat_content_from_openai_message_shape() -> None:
    content = extract_chat_content_from_response({"choices": [{"message": {"content": "hello"}}]})

    assert content == "hello"


def test_extract_chat_content_from_choices_text_shape() -> None:
    content = extract_chat_content_from_response({"choices": [{"text": "hello"}]})

    assert content == "hello"


def test_extract_chat_content_from_content_blocks_shape() -> None:
    content = extract_chat_content_from_response(
        {"choices": [{"message": {"content": [{"type": "text", "text": "hello"}]}}]}
    )

    assert content == "hello"


def test_extract_chat_content_from_output_text_shape() -> None:
    content = extract_chat_content_from_response({"output_text": "hello"})

    assert content == "hello"


def test_extract_chat_content_from_generated_text_shape() -> None:
    content = extract_chat_content_from_response({"generated_text": "hello"})

    assert content == "hello"


def test_extract_chat_content_from_reasoning_shape() -> None:
    content = extract_chat_content_from_response(
        {"choices": [{"message": {"content": None, "reasoning": "hello"}}]}
    )

    assert content == "hello"


def test_extract_chat_content_unsupported_shape_is_safe() -> None:
    with pytest.raises(VultrIntegrationError) as exc_info:
        extract_chat_content_from_response({"choices": [{"message": {"content": None}}], "secret": "raw"})

    error_text = str(exc_info.value)
    assert "Unable to extract assistant content" in error_text
    assert '"top_level_keys": ["choices", "secret"]' in error_text
    assert "SECRET_MODEL_OUTPUT" not in error_text


def test_summarize_response_shape_does_not_include_raw_content() -> None:
    summary = summarize_response_shape({"choices": [{"message": {"content": "SECRET_MODEL_OUTPUT"}}]})

    assert "SECRET_MODEL_OUTPUT" not in str(summary)
    assert summary["root_type"] == "dict"
    assert summary["has_content"] is True


@pytest.mark.parametrize(
    ("response_payload", "expected_content"),
    [
        (
            {"choices": [{"message": {"content": '{"status":"ok"}'}}]},
            '{"status":"ok"}',
        ),
        (
            {"choices": [{"text": '{"status":"ok"}'}]},
            '{"status":"ok"}',
        ),
        (
            {"choices": [{"message": {"content": [{"type": "text", "text": '{"status":"ok"}'}]}}]},
            '{"status":"ok"}',
        ),
        (
            {"output_text": '{"status":"ok"}'},
            '{"status":"ok"}',
        ),
        (
            {"response": '{"status":"ok"}'},
            '{"status":"ok"}',
        ),
        (
            {"content": '{"status":"ok"}'},
            '{"status":"ok"}',
        ),
        (
            {"generated_text": '{"status":"ok"}'},
            '{"status":"ok"}',
        ),
        (
            {"choices": [{"message": {"content": None, "reasoning": '{"status":"ok"}'}}]},
            '{"status":"ok"}',
        ),
    ],
)
def test_chat_completion_handles_supported_shapes(
    response_payload: dict[str, object],
    expected_content: str,
) -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["authorization"] = request.headers["Authorization"]
        captured["content_type"] = request.headers["Content-Type"]
        captured["payload"] = json.loads(request.content.decode("utf-8"))
        payload = dict(response_payload)
        payload["usage"] = {
            "prompt_tokens": 12,
            "completion_tokens": 4,
            "total_tokens": 16,
        }
        return httpx.Response(200, json=payload)

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
    assert result.content == expected_content
    assert result.latency_ms is not None
    assert result.usage is not None
    assert result.usage.total_tokens == 16
    assert result.response_shape_summary is not None
    assert captured["path"] == "/v1/chat/completions"
    assert str(captured["authorization"]).startswith("Bearer ")
    payload = captured["payload"]
    assert isinstance(payload, dict)
    assert payload["model"] == settings.chat_model
    assert payload["messages"][0]["role"] == "system"
    assert payload["messages"][1]["role"] == "user"


def test_chat_completion_returns_safe_error_for_unsupported_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={"choices": [{"message": {"content": None}}], "secret": "raw"})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, timeout=5.0) as http_client:
        client = VultrInferenceClient(
            VultrSettings(api_key="test-vultr-key"),
            http_client=http_client,
        )
        result = client.chat_completion(
            system_prompt="Return JSON.",
            user_prompt='{"status":"ok"}',
        )

    assert result.ok is False
    assert result.error_code == "VULTR_BAD_RESPONSE"
    assert "shape=" in (result.error_message or "")
    assert result.response_shape_summary is not None
    assert "SECRET_MODEL_OUTPUT" not in (result.error_message or "")


def test_chat_completion_returns_api_error_for_http_200_error_payload() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        del request
        return httpx.Response(200, json={"error": {"code": "bad_request", "message": "model unavailable"}})

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, timeout=5.0) as http_client:
        client = VultrInferenceClient(
            VultrSettings(api_key="test-vultr-key"),
            http_client=http_client,
        )
        result = client.chat_completion(
            system_prompt="Return JSON.",
            user_prompt='{"status":"ok"}',
        )

    assert result.ok is False
    assert result.error_code == "VULTR_API_ERROR"
    assert "model unavailable" in (result.error_message or "")


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
    assert result.latency_ms is not None
    assert "content" not in dumped


def test_extract_vendor_payment_fields_succeeds_after_retry_repair() -> None:
    responses = iter(
        [
            {"fields": {"invoice_id": "INV-1"}},
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
            },
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        payload = next(responses)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(payload)}}]},
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, timeout=5.0) as http_client:
        client = VultrInferenceClient(
            VultrSettings(api_key="test-vultr-key"),
            http_client=http_client,
        )
        result = client.extract_vendor_payment_fields(
            evidence={"invoice": {"doc_id": "invoice-1"}},
            required_fields=["invoice_id", "vendor_name", "amount", "bank_account_last4"],
        )

    assert result.ok is True
    assert result.fields["bank_account_last4"] == "8821"


def test_extract_vendor_payment_fields_fails_after_retry_if_still_invalid() -> None:
    responses = iter(
        [
            {"fields": {"invoice_id": "INV-1"}},
            {"fields": {"invoice_id": "INV-1", "vendor_name": "SECRET_MODEL_OUTPUT"}},
        ]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        del request
        payload = next(responses)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": json.dumps(payload)}}]},
        )

    transport = httpx.MockTransport(handler)
    with httpx.Client(transport=transport, timeout=5.0) as http_client:
        client = VultrInferenceClient(
            VultrSettings(api_key="test-vultr-key"),
            http_client=http_client,
        )
        result = client.extract_vendor_payment_fields(
            evidence={"invoice": {"doc_id": "invoice-1"}},
            required_fields=["invoice_id", "vendor_name", "amount", "bank_account_last4"],
        )

    dumped = json.dumps(result.model_dump(mode="json"))
    assert result.ok is False
    assert result.error_code == "VULTR_EXTRACTION_INVALID"
    assert "SECRET_MODEL_OUTPUT" not in dumped


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

    dumped = json.dumps(result.model_dump(mode="json"))
    assert result.ok is False
    assert result.error_code == "VULTR_EXTRACTION_INVALID"
    assert "not valid json" not in dumped


def test_vultr_settings_do_not_expose_api_key_in_repr_or_model_dump() -> None:
    settings = VultrSettings(api_key="super-secret-test-key")

    assert "super-secret-test-key" not in repr(settings)
    assert "super-secret-test-key" not in json.dumps(settings.model_dump(mode="json"))
