"""Environment-backed application settings for optional integrations."""

from __future__ import annotations

import os
from collections.abc import Callable

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

try:  # pragma: no cover - exercised via load_settings_from_env behavior.
    from dotenv import dotenv_values, find_dotenv
except ImportError:  # pragma: no cover - optional dependency guard.
    dotenv_values = None
    find_dotenv = None


_TRUE_VALUES = {"1", "true", "yes", "y", "on"}
_FALSE_VALUES = {"0", "false", "no", "n", "off"}


def _require_non_empty(value: str, field_name: str) -> str:
    """Reject blank string settings that would create ambiguous runtime behavior."""

    trimmed = value.strip()
    if not trimmed:
        raise ValueError(f"{field_name} cannot be empty")
    return trimmed


def _normalize_optional_secret(value: str | None) -> str | None:
    """Trim optional secret strings while preserving absence as None."""

    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _normalize_inference_base_url(value: str) -> str:
    """Normalize a Vultr inference URL or full chat endpoint into the base API URL."""

    trimmed = _require_non_empty(value, "vultr_inference_base_url").rstrip("/")
    suffix = "/chat/completions"
    if trimmed.lower().endswith(suffix):
        return trimmed[: -len(suffix)]
    return trimmed


def _read_first_env(
    read_env: Callable[[str, str | None], str | None],
    *names: str,
    default: str | None = None,
) -> str | None:
    """Return the first configured env value from a prioritized name list."""

    for name in names:
        value = read_env(name)
        if value is not None:
            return value
    return default


def _parse_bool_env(raw_value: str | None, *, field_name: str, default: bool) -> bool:
    """Parse string environment flags without relying on Python truthiness."""

    if raw_value is None:
        return default

    normalized = raw_value.strip().lower()
    if not normalized:
        return default
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False

    raise ValueError(
        f"{field_name} must be one of: true, false, 1, 0, yes, no, y, n, on, off"
    )


def _read_local_dotenv() -> dict[str, str]:
    """Read the nearest local .env file without mutating the process environment."""

    if find_dotenv is None or dotenv_values is None:
        return {}

    should_load = _parse_bool_env(
        os.getenv("TOSCO_LOAD_DOTENV"),
        field_name="TOSCO_LOAD_DOTENV",
        default=True,
    )
    if not should_load:
        return {}

    dotenv_path = find_dotenv(filename=".env", usecwd=True)
    if not dotenv_path:
        return {}

    return {
        key: value
        for key, value in dotenv_values(dotenv_path).items()
        if isinstance(key, str) and isinstance(value, str)
    }


class AppSettings(BaseModel):
    """Carry the env-configurable settings used by optional integrations."""

    model_config = ConfigDict(extra="forbid")

    vultr_api_key: str | None = None
    vultr_inference_base_url: str = "https://api.vultrinference.com/v1"
    vultr_chat_model: str = "qwen2.5-32b-instruct"
    tosco_fallback: bool = True
    tosco_use_system_trust_store: bool = True
    vultr_ca_bundle: str | None = None

    @field_validator("vultr_api_key", "vultr_ca_bundle", mode="before")
    @classmethod
    def normalize_optional_strings(cls, value: str | None) -> str | None:
        """Trim optional env strings and collapse blanks to None."""

        return _normalize_optional_secret(value)

    @field_validator("vultr_inference_base_url", "vultr_chat_model")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank integration configuration values."""

        if info.field_name == "vultr_inference_base_url":
            return _normalize_inference_base_url(value)
        return _require_non_empty(value, info.field_name)


def load_settings_from_env() -> AppSettings:
    """Read runtime settings from process env and an optional local .env file."""

    dotenv_overrides = _read_local_dotenv()

    def read_env(name: str, default: str | None = None) -> str | None:
        value = os.getenv(name)
        if value is not None:
            return value
        return dotenv_overrides.get(name, default)

    return AppSettings(
        vultr_api_key=_normalize_optional_secret(read_env("VULTR_API_KEY")),
        vultr_inference_base_url=_read_first_env(
            read_env,
            "VULTR_INFERENCE_URL",
            "VULTR_INFERENCE_BASE_URL",
            default="https://api.vultrinference.com/v1",
        ),
        vultr_chat_model=_read_first_env(
            read_env,
            "VULTR_MODEL",
            "VULTR_CHAT_MODEL",
            default="qwen2.5-32b-instruct",
        ),
        tosco_fallback=_parse_bool_env(
            read_env("TOSCO_FALLBACK"),
            field_name="TOSCO_FALLBACK",
            default=True,
        ),
        tosco_use_system_trust_store=_parse_bool_env(
            read_env("TOSCO_USE_SYSTEM_TRUST_STORE"),
            field_name="TOSCO_USE_SYSTEM_TRUST_STORE",
            default=True,
        ),
        vultr_ca_bundle=_normalize_optional_secret(read_env("VULTR_CA_BUNDLE")),
    )
