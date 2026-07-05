"""Safe Vultr Serverless Inference adapter for extraction-only tasks."""

from __future__ import annotations

import json
import re
import ssl
import time
from pathlib import Path
from typing import Any

import certifi
import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
import truststore

from app.models import canonical_json_hash


_VULTR_EXTRACTION_MAX_TOKENS = 1200
_CHAT_COMPLETIONS_SUFFIX = "/chat/completions"


def _require_non_empty(value: str, field_name: str) -> str:
    """Reject blank values that would produce ambiguous remote requests."""

    trimmed = value.strip()
    if not trimmed:
        raise ValueError(f"{field_name} cannot be empty")
    return trimmed


def _normalize_optional_secret(value: str | None) -> str | None:
    """Trim optional secrets while keeping unset values as None."""

    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _normalize_base_url(value: str) -> str:
    """Normalize a Vultr inference base URL or full chat endpoint into a base URL."""

    trimmed = _require_non_empty(value, "base_url").rstrip("/")
    if trimmed.lower().endswith(_CHAT_COMPLETIONS_SUFFIX):
        return trimmed[: -len(_CHAT_COMPLETIONS_SUFFIX)]
    return trimmed


class VultrIntegrationError(RuntimeError):
    """Signal invalid Vultr adapter usage or invalid response content."""


class ExtractionNormalizationError(VultrIntegrationError):
    """Signal invalid structured extraction payloads after JSON parsing."""


class VultrSettings(BaseModel):
    """Runtime configuration for the Vultr Serverless Inference client."""

    model_config = ConfigDict(extra="forbid")

    api_key: str | None = Field(default=None, repr=False, exclude=True)
    base_url: str = "https://api.vultrinference.com/v1"
    chat_model: str = "qwen2.5-32b-instruct"
    timeout_seconds: float = 30.0
    fallback_enabled: bool = True
    use_system_trust_store: bool = True
    ca_bundle: str | None = None

    @field_validator("api_key", "ca_bundle", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: str | None) -> str | None:
        """Trim optional settings and collapse blanks to None."""

        return _normalize_optional_secret(value)

    @field_validator("base_url", "chat_model")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank integration settings."""

        if info.field_name == "base_url":
            return _normalize_base_url(value)
        return _require_non_empty(value, info.field_name)

    @field_validator("timeout_seconds")
    @classmethod
    def validate_timeout_seconds(cls, value: float) -> float:
        """Reject non-positive HTTP timeouts."""

        if value <= 0:
            raise ValueError("timeout_seconds must be > 0")
        return value

    @property
    def configured(self) -> bool:
        """Report whether a non-empty API key is present."""

        return self.api_key is not None and bool(self.api_key.strip())


def build_httpx_verify_config(settings: VultrSettings) -> str | ssl.SSLContext | bool:
    """Build explicit certificate verification config for one Vultr HTTP client."""

    if settings.ca_bundle is not None:
        bundle_path = Path(settings.ca_bundle).expanduser()
        if not bundle_path.exists():
            raise VultrIntegrationError(
                "Configured VULTR_CA_BUNDLE was not found. Provide a valid PEM bundle path."
            )
        return str(bundle_path)

    if settings.use_system_trust_store:
        return truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    return certifi.where()


class VultrUsage(BaseModel):
    """Token-usage metadata returned by the chat completion API."""

    model_config = ConfigDict(extra="forbid")

    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None

    @field_validator("prompt_tokens", "completion_tokens", "total_tokens")
    @classmethod
    def validate_usage_counts(cls, value: int | None, info: ValidationInfo) -> int | None:
        """Reject negative usage counters."""

        if value is not None and value < 0:
            raise ValueError(f"{info.field_name} must be >= 0")
        return value


class VultrChatResult(BaseModel):
    """Safe, non-secret result model for one Vultr chat completion call."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    model: str
    content: str | None = None
    usage: VultrUsage | None = None
    error_code: str | None = None
    error_message: str | None = None
    response_shape_summary: dict[str, Any] | None = None
    fallback_used: bool = False
    latency_ms: int | None = None

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        """Reject blank model names."""

        return _require_non_empty(value, "model")


class VultrExtractionResult(BaseModel):
    """Safe extraction result that never stores raw model output."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    fields: dict[str, Any] = Field(default_factory=dict)
    source_spans: dict[str, list[int]] = Field(default_factory=dict)
    model: str
    raw_content_hash: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    fallback_used: bool = False
    latency_ms: int | None = None

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        """Reject blank model names."""

        return _require_non_empty(value, "model")

    @field_validator("latency_ms")
    @classmethod
    def validate_latency_ms(cls, value: int | None) -> int | None:
        """Reject negative extraction latency values."""

        if value is not None and value < 0:
            raise ValueError("latency_ms must be >= 0")
        return value


def summarize_response_shape(data: Any) -> dict[str, Any]:
    """Return safe response-shape metadata without storing model output text."""

    top_level_keys: list[str] | None = None
    choices_type: str | None = None
    first_choice_keys: list[str] | None = None
    message_keys: list[str] | None = None
    has_output_text = False
    has_content = False
    has_error = False

    if isinstance(data, dict):
        top_level_keys = sorted(str(key) for key in data.keys())
        choices = data.get("choices")
        if "choices" in data:
            choices_type = type(choices).__name__
        if isinstance(choices, list) and choices:
            first_choice = choices[0]
            if isinstance(first_choice, dict):
                first_choice_keys = sorted(str(key) for key in first_choice.keys())
                message = first_choice.get("message")
                if isinstance(message, dict):
                    message_keys = sorted(str(key) for key in message.keys())
                    has_content = "content" in message
                if "text" in first_choice:
                    has_content = True
        has_output_text = "output_text" in data
        has_content = has_content or any(
            key in data for key in ("response", "content", "generated_text")
        )
        has_error = "error" in data

    return {
        "root_type": type(data).__name__,
        "top_level_keys": top_level_keys,
        "choices_type": choices_type,
        "first_choice_keys": first_choice_keys,
        "message_keys": message_keys,
        "has_output_text": has_output_text,
        "has_content": has_content,
        "has_error": has_error,
    }


def _shape_summary_json(data: Any) -> str:
    """Serialize a safe response-shape summary for logs and error messages."""

    return json.dumps(summarize_response_shape(data), sort_keys=True)


def _coerce_text(value: Any) -> str | None:
    """Return a stripped non-empty text value or None."""

    if not isinstance(value, str):
        return None
    stripped = value.strip()
    return stripped or None


def _join_text_blocks(value: Any) -> str | None:
    """Join list-based text blocks from message content structures."""

    if not isinstance(value, list):
        return None

    text_parts: list[str] = []
    for item in value:
        if isinstance(item, str):
            text_value = item.strip()
            if text_value:
                text_parts.append(text_value)
            continue
        if not isinstance(item, dict):
            continue
        text_value = _coerce_text(item.get("text"))
        if text_value is not None:
            text_parts.append(text_value)

    if not text_parts:
        return None
    return "".join(text_parts)


def _extract_text_value(value: Any) -> str | None:
    """Extract text from string, list-block, or small nested dict containers."""

    direct_text = _coerce_text(value)
    if direct_text is not None:
        return direct_text

    block_text = _join_text_blocks(value)
    if block_text is not None:
        return block_text

    if not isinstance(value, dict):
        return None

    for key in ("text", "content", "response", "output_text", "generated_text", "reasoning"):
        nested_text = _extract_text_value(value.get(key))
        if nested_text is not None:
            return nested_text

    return None


def _safe_error_message(error_payload: Any) -> str:
    """Summarize API error payloads without exposing request metadata."""

    if isinstance(error_payload, dict):
        code = _coerce_text(error_payload.get("code"))
        message = _coerce_text(error_payload.get("message"))
        if code and message:
            return f"Vultr API returned an error payload: {code}: {message}"
        if code:
            return f"Vultr API returned an error payload: {code}"
        if message:
            return f"Vultr API returned an error payload: {message}"
        return "Vultr API returned an error payload."
    if isinstance(error_payload, list):
        return "Vultr API returned an error payload."
    error_text = _coerce_text(error_payload)
    if error_text is not None:
        return f"Vultr API returned an error payload: {error_text}"
    return "Vultr API returned an error payload."


def extract_chat_content_from_response(data: dict[str, Any]) -> str:
    """Extract assistant text from several OpenAI-compatible response shapes."""

    if "error" in data:
        summary = _shape_summary_json(data)
        raise VultrIntegrationError(
            f"{_safe_error_message(data.get('error'))} shape={summary}"
        )

    choices = data.get("choices")
    if isinstance(choices, list) and choices:
        first_choice = choices[0]
        if isinstance(first_choice, dict):
            message = first_choice.get("message")
            if isinstance(message, dict):
                content_text = _extract_text_value(message.get("content"))
                if content_text is not None:
                    return content_text
                reasoning_text = _extract_text_value(message.get("reasoning"))
                if reasoning_text is not None:
                    return reasoning_text

            choice_text = _extract_text_value(first_choice.get("text"))
            if choice_text is not None:
                return choice_text

    for key in ("output_text", "response", "content", "generated_text"):
        direct_text = _extract_text_value(data.get(key))
        if direct_text is not None:
            return direct_text

    summary = _shape_summary_json(data)
    raise VultrIntegrationError(
        "Unable to extract assistant content from Vultr response shape. "
        f"shape={summary}"
    )


def find_first_json_object(text: str) -> str:
    """Find the first balanced JSON object substring inside free-form text."""

    in_string = False
    escape_next = False
    depth = 0
    start_index: int | None = None

    for index, char in enumerate(text):
        if start_index is None:
            if char == "{":
                start_index = index
                depth = 1
            continue

        if escape_next:
            escape_next = False
            continue

        if char == "\\" and in_string:
            escape_next = True
            continue

        if char == '"':
            in_string = not in_string
            continue

        if in_string:
            continue

        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start_index : index + 1]

    raise VultrIntegrationError("Invalid JSON object response.")


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse a plain or fenced JSON object and reject non-object payloads."""

    candidate = text.strip()
    if candidate.startswith("```"):
        match = re.search(r"```(?:json)?\s*(.*?)\s*```", candidate, flags=re.IGNORECASE | re.DOTALL)
        if match is not None:
            candidate = match.group(1).strip()

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        candidate = find_first_json_object(candidate)
        try:
            payload = json.loads(candidate)
        except json.JSONDecodeError as exc:
            raise VultrIntegrationError("Invalid JSON object response.") from exc

    if not isinstance(payload, dict):
        raise VultrIntegrationError("JSON payload must be an object.")

    return payload


def _normalize_span_item(value: Any, *, field_name: str) -> int:
    """Normalize one source-span value into an integer reference."""

    if isinstance(value, bool) or value is None:
        raise ExtractionNormalizationError(
            f"Required field '{field_name}' must have integer source spans."
        )

    if isinstance(value, int):
        if value <= 0:
            raise ExtractionNormalizationError(
                f"Required field '{field_name}' must have positive integer source spans."
            )
        return value

    if isinstance(value, str):
        candidate = value.strip()
        if candidate.isdigit():
            normalized = int(candidate)
            if normalized <= 0:
                raise ExtractionNormalizationError(
                    f"Required field '{field_name}' must have positive integer source spans."
                )
            return normalized

    raise ExtractionNormalizationError(
        f"Required field '{field_name}' must have integer source spans."
    )


def _normalize_source_spans(value: Any, *, field_name: str) -> list[int]:
    """Normalize supported source-span shapes into a non-empty integer list."""

    if isinstance(value, list):
        normalized = [_normalize_span_item(item, field_name=field_name) for item in value]
    else:
        normalized = [_normalize_span_item(value, field_name=field_name)]

    if not normalized:
        raise ExtractionNormalizationError(
            f"Required field '{field_name}' must have non-empty source spans."
        )

    return normalized


def _normalize_amount(value: Any) -> int | float:
    """Normalize supported amount formats into a positive numeric value."""

    if isinstance(value, bool) or value is None:
        raise ExtractionNormalizationError("Required extracted field 'amount' must be numeric.")

    if isinstance(value, int):
        if value <= 0:
            raise ExtractionNormalizationError("Required extracted field 'amount' must be > 0.")
        return value

    if isinstance(value, float):
        if value <= 0:
            raise ExtractionNormalizationError("Required extracted field 'amount' must be > 0.")
        return int(value) if value.is_integer() else value

    if isinstance(value, str):
        cleaned = value.strip().replace(",", "").replace("$", "")
        if not cleaned:
            raise ExtractionNormalizationError("Required extracted field 'amount' must be numeric.")
        try:
            normalized = float(cleaned)
        except ValueError as exc:
            raise ExtractionNormalizationError(
                "Required extracted field 'amount' must be numeric."
            ) from exc
        if normalized <= 0:
            raise ExtractionNormalizationError("Required extracted field 'amount' must be > 0.")
        return int(normalized) if normalized.is_integer() else normalized

    raise ExtractionNormalizationError("Required extracted field 'amount' must be numeric.")


def _normalize_bank_account_last4(value: Any) -> str:
    """Normalize bank account suffixes into exactly four digits."""

    if isinstance(value, bool) or value is None:
        raise ExtractionNormalizationError(
            "Required extracted field 'bank_account_last4' must be exactly four digits."
        )

    digits = re.sub(r"\D", "", str(value))
    if len(digits) < 4:
        raise ExtractionNormalizationError(
            "Required extracted field 'bank_account_last4' must be exactly four digits."
        )

    suffix = digits[-4:]
    if len(suffix) != 4 or not suffix.isdigit():
        raise ExtractionNormalizationError(
            "Required extracted field 'bank_account_last4' must be exactly four digits."
        )
    return suffix


def _normalize_required_field_value(field_name: str, value: Any) -> Any:
    """Normalize supported required field types."""

    if field_name == "amount":
        return _normalize_amount(value)

    if field_name == "bank_account_last4":
        return _normalize_bank_account_last4(value)

    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            raise ExtractionNormalizationError(
                f"Required extracted field '{field_name}' is blank."
            )
        return stripped

    if isinstance(value, bool) or value is None:
        raise ExtractionNormalizationError(
            f"Required extracted field '{field_name}' is missing or blank."
        )

    if isinstance(value, (int, float)):
        return int(value) if isinstance(value, float) and value.is_integer() else value

    raise ExtractionNormalizationError(
        f"Required extracted field '{field_name}' has an unsupported type."
    )


def normalize_extraction_payload(
    payload: dict[str, Any],
    *,
    required_fields: list[str],
) -> tuple[dict[str, Any], dict[str, list[int]]]:
    """Normalize supported extraction payload variants into canonical fields/source_spans."""

    candidate = payload.get("data") if isinstance(payload.get("data"), dict) else payload

    raw_fields: dict[str, Any] = {}
    if isinstance(candidate.get("fields"), dict):
        raw_fields.update(candidate["fields"])
    if isinstance(candidate.get("extracted_fields"), dict):
        raw_fields.update(candidate["extracted_fields"])
    for field_name in required_fields:
        if field_name in candidate and field_name not in raw_fields:
            raw_fields[field_name] = candidate[field_name]

    if not raw_fields:
        raise ExtractionNormalizationError("Extraction payload is missing required fields.")

    raw_sources = None
    if isinstance(candidate.get("source_spans"), dict):
        raw_sources = candidate["source_spans"]
    elif isinstance(candidate.get("sources"), dict):
        raw_sources = candidate["sources"]

    if raw_sources is None:
        raise ExtractionNormalizationError("Extraction payload is missing source_spans.")

    normalized_fields: dict[str, Any] = {}
    normalized_sources: dict[str, list[int]] = {}

    for field_name in required_fields:
        if field_name not in raw_fields:
            raise ExtractionNormalizationError(
                f"Missing required extracted field '{field_name}'."
            )
        if field_name not in raw_sources:
            raise ExtractionNormalizationError(
                f"Required field '{field_name}' must have non-empty source spans."
            )

        normalized_fields[field_name] = _normalize_required_field_value(
            field_name,
            raw_fields[field_name],
        )
        normalized_sources[field_name] = _normalize_source_spans(
            raw_sources[field_name],
            field_name=field_name,
        )

    return normalized_fields, normalized_sources


def _usage_from_payload(value: Any) -> VultrUsage | None:
    """Parse optional usage metadata from an OpenAI-compatible response body."""

    if not isinstance(value, dict):
        return None

    return VultrUsage(
        prompt_tokens=value.get("prompt_tokens"),
        completion_tokens=value.get("completion_tokens"),
        total_tokens=value.get("total_tokens"),
    )


class VultrInferenceClient:
    """HTTP client for Vultr Serverless Inference chat-completion requests."""

    def __init__(
        self,
        settings: VultrSettings,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        if http_client is not None:
            self._http_client = http_client
            return

        verify_config = build_httpx_verify_config(settings)
        self._http_client = httpx.Client(
            timeout=settings.timeout_seconds,
            verify=verify_config,
        )

    def _headers(self) -> dict[str, str]:
        """Build authenticated request headers without exposing the API key."""

        if not self.settings.configured:
            raise VultrIntegrationError("Vultr API key is not configured.")

        return {
            "Authorization": f"Bearer {self.settings.api_key}",
            "Content-Type": "application/json",
        }

    def _url(self, path: str) -> str:
        """Join a relative API path against the configured base URL."""

        return f"{self.settings.base_url.rstrip('/')}/{path.lstrip('/')}"

    def chat_completion(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 700,
    ) -> VultrChatResult:
        """Perform one chat completion request and return a safe result model."""

        if not self.settings.configured:
            return VultrChatResult(
                ok=False,
                model=self.settings.chat_model,
                error_code="VULTR_NOT_CONFIGURED",
                error_message="Vultr API key is not configured.",
                fallback_used=True,
            )

        payload = {
            "model": self.settings.chat_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        started_at = time.perf_counter()

        try:
            response = self._http_client.post(
                self._url("/chat/completions"),
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            latency_ms = max(0, round((time.perf_counter() - started_at) * 1000))
            status_code = None
            if isinstance(exc, httpx.HTTPStatusError):
                status_code = exc.response.status_code
            error_code = "VULTR_HTTP_ERROR"
            error_message = (
                f"Vultr request failed with HTTP {status_code}."
                if status_code is not None
                else "Vultr request failed before a valid response was received."
            )
            if isinstance(exc, httpx.ConnectError) and "certificate verify failed" in str(exc).lower():
                error_code = "VULTR_TLS_VERIFY_FAILED"
                error_message = (
                    "TLS certificate verification failed. "
                    "Check the local trust store or configure VULTR_CA_BUNDLE."
                )
            return VultrChatResult(
                ok=False,
                model=self.settings.chat_model,
                error_code=error_code,
                error_message=error_message,
                response_shape_summary=None,
                fallback_used=True,
                latency_ms=latency_ms,
            )

        latency_ms = max(0, round((time.perf_counter() - started_at) * 1000))
        try:
            response_payload = response.json()
            if not isinstance(response_payload, dict):
                response_shape_summary = summarize_response_shape(response_payload)
                return VultrChatResult(
                    ok=False,
                    model=self.settings.chat_model,
                    error_code="VULTR_BAD_RESPONSE",
                    error_message=(
                        "Vultr returned a non-object chat completion payload. "
                        f"shape={json.dumps(response_shape_summary, sort_keys=True)}"
                    ),
                    response_shape_summary=response_shape_summary,
                    fallback_used=True,
                    latency_ms=latency_ms,
                )
            response_shape_summary = summarize_response_shape(response_payload)
            if "error" in response_payload:
                return VultrChatResult(
                    ok=False,
                    model=self.settings.chat_model,
                    error_code="VULTR_API_ERROR",
                    error_message=(
                        f"{_safe_error_message(response_payload.get('error'))} "
                        f"shape={json.dumps(response_shape_summary, sort_keys=True)}"
                    ),
                    response_shape_summary=response_shape_summary,
                    fallback_used=True,
                    latency_ms=latency_ms,
                )
            content = extract_chat_content_from_response(response_payload)
            usage = _usage_from_payload(response_payload.get("usage"))
        except (TypeError, json.JSONDecodeError):
            return VultrChatResult(
                ok=False,
                model=self.settings.chat_model,
                error_code="VULTR_BAD_RESPONSE",
                error_message="Vultr returned an invalid chat completion payload.",
                response_shape_summary=None,
                fallback_used=True,
                latency_ms=latency_ms,
            )
        except VultrIntegrationError as exc:
            response_shape_summary = None
            if "response_payload" in locals():
                response_shape_summary = summarize_response_shape(response_payload)
            return VultrChatResult(
                ok=False,
                model=self.settings.chat_model,
                error_code="VULTR_BAD_RESPONSE",
                error_message=str(exc),
                response_shape_summary=response_shape_summary,
                fallback_used=True,
                latency_ms=latency_ms,
            )

        return VultrChatResult(
            ok=True,
            model=self.settings.chat_model,
            content=content,
            usage=usage,
            response_shape_summary=response_shape_summary,
            latency_ms=latency_ms,
        )

    def list_models(self) -> dict[str, Any]:
        """Return the raw model-list JSON for manual debug or verification."""

        if not self.settings.configured:
            raise VultrIntegrationError("Vultr API key is not configured.")

        response = self._http_client.get(self._url("/models"), headers=self._headers())
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise VultrIntegrationError("Vultr model listing must return a JSON object.")
        return payload

    def _repair_extraction_content(
        self,
        *,
        required_fields: list[str],
        response_schema: dict[str, Any],
        previous_payload: dict[str, Any] | None,
        previous_content: str,
    ) -> VultrChatResult:
        """Ask Vultr once to rewrite a prior extraction into the canonical schema."""

        canonical_schema_text = json.dumps(
            response_schema,
            sort_keys=True,
            separators=(",", ":"),
        )
        if previous_payload is not None:
            previous_value = json.dumps(
                previous_payload,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
            previous_label = "previous_payload_json"
        else:
            previous_value = previous_content
            previous_label = "previous_response_text"

        truncated_previous = previous_value[:1500]
        repair_prompt = (
            "Transform the previous extraction output into the exact canonical schema below. "
            "Return ONLY one JSON object. Do not include markdown, prose, reasoning, comments, "
            "or explanations.\n"
            f"required_fields={json.dumps(required_fields, separators=(',', ':'))}\n"
            f"canonical_schema={canonical_schema_text}\n"
            f"{previous_label}={truncated_previous}\n"
            "Rules:\n"
            "- source_spans must use integer line/page/span references.\n"
            "- If exact spans are unavailable, use [1] for fields found in the provided evidence.\n"
            "- bank_account_last4 must be exactly four digits as a string.\n"
            "- Return no other text."
        )
        return self.chat_completion(
            system_prompt=(
                "You are a JSON repair function for a financial clearance system. "
                "Return ONLY one JSON object in the exact canonical schema. "
                "Do not approve or block. Do not add any prose."
            ),
            user_prompt=repair_prompt,
            temperature=0.0,
            max_tokens=_VULTR_EXTRACTION_MAX_TOKENS,
        )

    def extract_vendor_payment_fields(
        self,
        *,
        evidence: dict[str, Any],
        required_fields: list[str],
    ) -> VultrExtractionResult:
        """Extract vendor-payment fields as strict JSON without allowing model verdicts."""

        system_prompt = (
            "You are a JSON extraction function for a financial clearance system. "
            "Return ONLY one JSON object. Do not include markdown, prose, reasoning, comments, "
            "or explanations. Do not decide whether payment is allowed. Do not approve or block. "
            "Extract only typed fields from the evidence."
        )
        response_schema = {
            "fields": {
                "invoice_id": "...",
                "vendor_name": "...",
                "amount": 0,
                "bank_account_last4": "0000",
            },
            "source_spans": {
                "invoice_id": [1],
                "vendor_name": [1],
                "amount": [1],
                "bank_account_last4": [1],
            },
        }
        user_prompt = (
            "Return ONLY one JSON object using this exact schema:\n"
            f"{json.dumps(response_schema, indent=2, sort_keys=True)}\n"
            "Rules:\n"
            "- source_spans must use integer line/page/span references.\n"
            "- If exact spans are unavailable, use [1] for fields found in the provided evidence.\n"
            "- bank_account_last4 must be exactly four digits as a string.\n"
            "- Return no other text.\n"
            f"required_fields={json.dumps(required_fields, separators=(',', ':'))}\n"
            "evidence="
            + json.dumps(
                evidence,
                sort_keys=True,
                separators=(",", ":"),
                default=str,
            )
        )

        chat_result = self.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0,
            max_tokens=_VULTR_EXTRACTION_MAX_TOKENS,
        )
        total_latency_ms = chat_result.latency_ms
        if not chat_result.ok or chat_result.content is None:
            return VultrExtractionResult(
                ok=False,
                model=chat_result.model,
                error_code=chat_result.error_code,
                error_message=chat_result.error_message,
                fallback_used=chat_result.fallback_used,
                latency_ms=total_latency_ms,
            )

        raw_content_hash = canonical_json_hash({"content": chat_result.content})
        parsed_payload: dict[str, Any] | None = None
        try:
            parsed_payload = extract_json_object(chat_result.content)
            fields, source_spans = normalize_extraction_payload(
                parsed_payload,
                required_fields=required_fields,
            )
        except VultrIntegrationError as exc:
            repair_result = self._repair_extraction_content(
                required_fields=required_fields,
                response_schema=response_schema,
                previous_payload=parsed_payload,
                previous_content=chat_result.content,
            )
            if not repair_result.ok or repair_result.content is None:
                if repair_result.latency_ms is not None:
                    total_latency_ms = (total_latency_ms or 0) + repair_result.latency_ms
                return VultrExtractionResult(
                    ok=False,
                    model=repair_result.model,
                    raw_content_hash=raw_content_hash,
                    error_code="VULTR_EXTRACTION_INVALID",
                    error_message="Vultr extraction did not produce required fields/source_spans after retry.",
                    fallback_used=repair_result.fallback_used,
                    latency_ms=total_latency_ms,
                )

            if repair_result.latency_ms is not None:
                total_latency_ms = (total_latency_ms or 0) + repair_result.latency_ms
            raw_content_hash = canonical_json_hash({"content": repair_result.content})
            try:
                repaired_payload = extract_json_object(repair_result.content)
                fields, source_spans = normalize_extraction_payload(
                    repaired_payload,
                    required_fields=required_fields,
                )
            except VultrIntegrationError:
                return VultrExtractionResult(
                    ok=False,
                    model=repair_result.model,
                    raw_content_hash=raw_content_hash,
                    error_code="VULTR_EXTRACTION_INVALID",
                    error_message="Vultr extraction did not produce required fields/source_spans after retry.",
                    fallback_used=repair_result.fallback_used,
                    latency_ms=total_latency_ms,
                )

        return VultrExtractionResult(
            ok=True,
            fields=fields,
            source_spans={key: list(value) for key, value in source_spans.items() if isinstance(value, list)},
            model=chat_result.model,
            raw_content_hash=raw_content_hash,
            fallback_used=False,
            latency_ms=total_latency_ms,
        )
