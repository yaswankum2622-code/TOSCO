from __future__ import annotations

import ssl

import certifi
import pytest

from app.integrations.vultr import (
    VultrIntegrationError,
    VultrSettings,
    build_httpx_verify_config,
)


def test_default_tls_verify_uses_system_trust_store() -> None:
    verify_config = build_httpx_verify_config(VultrSettings(api_key="test-key"))

    assert isinstance(verify_config, ssl.SSLContext)
    assert verify_config is not False


def test_ca_bundle_takes_priority_over_system_trust_store(tmp_path) -> None:
    bundle_path = tmp_path / "corp-bundle.pem"
    bundle_path.write_text("not-a-real-pem-but-good-enough-for-path-testing", encoding="utf-8")

    verify_config = build_httpx_verify_config(
        VultrSettings(
            api_key="test-key",
            use_system_trust_store=True,
            ca_bundle=str(bundle_path),
        )
    )

    assert verify_config == str(bundle_path)
    assert verify_config is not False


def test_missing_ca_bundle_path_raises_safe_error() -> None:
    with pytest.raises(VultrIntegrationError, match="VULTR_CA_BUNDLE"):
        build_httpx_verify_config(
            VultrSettings(
                api_key="test-key",
                ca_bundle="C:\\missing\\bundle.pem",
            )
        )


def test_disabling_system_trust_store_uses_certifi_bundle() -> None:
    verify_config = build_httpx_verify_config(
        VultrSettings(
            api_key="test-key",
            use_system_trust_store=False,
        )
    )

    assert verify_config == certifi.where()
    assert verify_config is not False


def test_verify_config_never_returns_false() -> None:
    default_verify = build_httpx_verify_config(VultrSettings(api_key="test-key"))
    certifi_verify = build_httpx_verify_config(
        VultrSettings(api_key="test-key", use_system_trust_store=False)
    )

    assert default_verify is not False
    assert certifi_verify is not False
