"""Environment-backed application settings for optional integrations."""

from __future__ import annotations

import os

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator


_TRUE_VALUES = {"1", "true", "yes", "on"}
_FALSE_VALUES = {"0", "false", "no", "off"}


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
        f"{field_name} must be one of: true, false, 1, 0, yes, no, on, off"
    )


class AppSettings(BaseModel):
    """Carry the env-configurable settings used by optional integrations."""

    model_config = ConfigDict(extra="forbid")

    vultr_api_key: str | None = None
    vultr_inference_base_url: str = "https://api.vultrinference.com/v1"
    vultr_chat_model: str = "nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16"
    tosco_fallback: bool = True

    @field_validator("vultr_api_key", mode="before")
    @classmethod
    def normalize_api_key(cls, value: str | None) -> str | None:
        """Trim optional API keys and collapse blanks to None."""

        return _normalize_optional_secret(value)

    @field_validator("vultr_inference_base_url", "vultr_chat_model")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank integration configuration values."""

        return _require_non_empty(value, info.field_name)


def load_settings_from_env() -> AppSettings:
    """Read runtime settings from the process environment without logging secrets."""

    return AppSettings(
        vultr_api_key=_normalize_optional_secret(os.getenv("VULTR_API_KEY")),
        vultr_inference_base_url=os.getenv(
            "VULTR_INFERENCE_BASE_URL",
            "https://api.vultrinference.com/v1",
        ),
        vultr_chat_model=os.getenv(
            "VULTR_CHAT_MODEL",
            "nvidia/Nemotron-3-Nano-Omni-30B-A3B-Reasoning-BF16",
        ),
        tosco_fallback=_parse_bool_env(
            os.getenv("TOSCO_FALLBACK"),
            field_name="TOSCO_FALLBACK",
            default=True,
        ),
    )
