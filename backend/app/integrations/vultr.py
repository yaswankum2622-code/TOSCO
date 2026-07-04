"""Safe Vultr Serverless Inference adapter for extraction-only tasks."""

from __future__ import annotations

import json
import re
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.models import canonical_json_hash


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


class VultrIntegrationError(RuntimeError):
    """Signal invalid Vultr adapter usage or invalid response content."""


class VultrSettings(BaseModel):
    """Runtime configuration for the Vultr Serverless Inference client."""

    model_config = ConfigDict(extra="forbid")

    api_key: str | None = Field(default=None, repr=False, exclude=True)
    base_url: str = "https://api.vultrinference.com/v1"
    chat_model: str = "nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16"
    timeout_seconds: float = 30.0
    fallback_enabled: bool = True

    @field_validator("api_key", mode="before")
    @classmethod
    def normalize_api_key(cls, value: str | None) -> str | None:
        """Trim optional API keys and collapse blanks to None."""

        return _normalize_optional_secret(value)

    @field_validator("base_url", "chat_model")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank integration settings."""

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
    fallback_used: bool = False

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

    @field_validator("model")
    @classmethod
    def validate_model(cls, value: str) -> str:
        """Reject blank model names."""

        return _require_non_empty(value, "model")


def extract_json_object(text: str) -> dict[str, Any]:
    """Parse a plain or fenced JSON object and reject non-object payloads."""

    candidate = text.strip()
    if candidate.startswith("```"):
        match = re.fullmatch(r"```(?:json)?\s*(.*?)\s*```", candidate, flags=re.IGNORECASE | re.DOTALL)
        if match is None:
            raise VultrIntegrationError("Invalid fenced JSON block.")
        candidate = match.group(1).strip()

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise VultrIntegrationError("Invalid JSON object response.") from exc

    if not isinstance(payload, dict):
        raise VultrIntegrationError("JSON payload must be an object.")

    return payload


def _usage_from_payload(value: Any) -> VultrUsage | None:
    """Parse optional usage metadata from an OpenAI-compatible response body."""

    if not isinstance(value, dict):
        return None

    return VultrUsage(
        prompt_tokens=value.get("prompt_tokens"),
        completion_tokens=value.get("completion_tokens"),
        total_tokens=value.get("total_tokens"),
    )


def _first_message_content(payload: dict[str, Any]) -> str:
    """Extract the first assistant message content from a chat completion payload."""

    choices = payload.get("choices")
    if not isinstance(choices, list) or not choices:
        raise ValueError("choices[0] is missing")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise ValueError("choices[0] must be an object")

    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise ValueError("choices[0].message must be an object")

    content = message.get("content")
    if isinstance(content, str):
        return content

    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if not isinstance(item, dict):
                continue
            text_value = item.get("text")
            if isinstance(text_value, str):
                text_parts.append(text_value)
        joined = "".join(text_parts)
        if joined:
            return joined

    raise ValueError("choices[0].message.content must be a string")


class VultrInferenceClient:
    """HTTP client for Vultr Serverless Inference chat-completion requests."""

    def __init__(
        self,
        settings: VultrSettings,
        http_client: httpx.Client | None = None,
    ) -> None:
        self.settings = settings
        self._http_client = http_client or httpx.Client(timeout=settings.timeout_seconds)

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

        try:
            response = self._http_client.post(
                self._url("/chat/completions"),
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            status_code = None
            if isinstance(exc, httpx.HTTPStatusError):
                status_code = exc.response.status_code
            return VultrChatResult(
                ok=False,
                model=self.settings.chat_model,
                error_code="VULTR_HTTP_ERROR",
                error_message=(
                    f"Vultr request failed with HTTP {status_code}."
                    if status_code is not None
                    else "Vultr request failed before a valid response was received."
                ),
                fallback_used=True,
            )

        try:
            response_payload = response.json()
            if not isinstance(response_payload, dict):
                raise ValueError("response body must be an object")
            content = _first_message_content(response_payload)
            usage = _usage_from_payload(response_payload.get("usage"))
        except (ValueError, TypeError, json.JSONDecodeError):
            return VultrChatResult(
                ok=False,
                model=self.settings.chat_model,
                error_code="VULTR_BAD_RESPONSE",
                error_message="Vultr returned an invalid chat completion payload.",
                fallback_used=True,
            )

        return VultrChatResult(
            ok=True,
            model=self.settings.chat_model,
            content=content,
            usage=usage,
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

    def extract_vendor_payment_fields(
        self,
        *,
        evidence: dict[str, Any],
        required_fields: list[str],
    ) -> VultrExtractionResult:
        """Extract vendor-payment fields as strict JSON without allowing model verdicts."""

        system_prompt = (
            "You extract vendor-payment fields for a financial clearance system. "
            "Return strict JSON only. Do not decide whether payment is allowed."
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
        user_prompt = json.dumps(
            {
                "required_fields": required_fields,
                "evidence": evidence,
                "response_schema": response_schema,
            },
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        )

        chat_result = self.chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            temperature=0.0,
            max_tokens=700,
        )
        if not chat_result.ok or chat_result.content is None:
            return VultrExtractionResult(
                ok=False,
                model=chat_result.model,
                error_code=chat_result.error_code,
                error_message=chat_result.error_message,
                fallback_used=chat_result.fallback_used,
            )

        try:
            payload = extract_json_object(chat_result.content)
        except VultrIntegrationError as exc:
            return VultrExtractionResult(
                ok=False,
                model=chat_result.model,
                raw_content_hash=canonical_json_hash({"content": chat_result.content}),
                error_code="VULTR_JSON_PARSE_ERROR",
                error_message=str(exc),
                fallback_used=chat_result.fallback_used,
            )

        fields = payload.get("fields")
        source_spans = payload.get("source_spans")
        if not isinstance(fields, dict) or not isinstance(source_spans, dict):
            return VultrExtractionResult(
                ok=False,
                model=chat_result.model,
                raw_content_hash=canonical_json_hash({"content": chat_result.content}),
                error_code="VULTR_EXTRACTION_INVALID",
                error_message="Vultr extraction must return object fields and source_spans.",
                fallback_used=chat_result.fallback_used,
            )

        for field_name in required_fields:
            field_value = fields.get(field_name)
            spans = source_spans.get(field_name)
            if field_value is None:
                return VultrExtractionResult(
                    ok=False,
                    model=chat_result.model,
                    raw_content_hash=canonical_json_hash({"content": chat_result.content}),
                    error_code="VULTR_EXTRACTION_INVALID",
                    error_message=f"Missing required extracted field '{field_name}'.",
                    fallback_used=chat_result.fallback_used,
                )
            if isinstance(field_value, str) and not field_value.strip():
                return VultrExtractionResult(
                    ok=False,
                    model=chat_result.model,
                    raw_content_hash=canonical_json_hash({"content": chat_result.content}),
                    error_code="VULTR_EXTRACTION_INVALID",
                    error_message=f"Required extracted field '{field_name}' is blank.",
                    fallback_used=chat_result.fallback_used,
                )
            if not isinstance(spans, list) or not spans or any(not isinstance(item, int) for item in spans):
                return VultrExtractionResult(
                    ok=False,
                    model=chat_result.model,
                    raw_content_hash=canonical_json_hash({"content": chat_result.content}),
                    error_code="VULTR_EXTRACTION_INVALID",
                    error_message=f"Required field '{field_name}' must have non-empty source spans.",
                    fallback_used=chat_result.fallback_used,
                )

        return VultrExtractionResult(
            ok=True,
            fields=fields,
            source_spans={key: list(value) for key, value in source_spans.items() if isinstance(value, list)},
            model=chat_result.model,
            raw_content_hash=canonical_json_hash({"content": chat_result.content}),
            fallback_used=False,
        )
