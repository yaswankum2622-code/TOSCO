from __future__ import annotations

from app.config import load_settings_from_env


def test_load_settings_from_env_reads_process_values(monkeypatch) -> None:
    monkeypatch.setenv("TOSCO_LOAD_DOTENV", "false")
    monkeypatch.setenv("VULTR_API_KEY", "process-key")
    monkeypatch.setenv("VULTR_INFERENCE_URL", "https://example.test/v1/chat/completions")
    monkeypatch.setenv("VULTR_MODEL", "example/model")
    monkeypatch.setenv("TOSCO_FALLBACK", "n")
    monkeypatch.setenv("TOSCO_USE_SYSTEM_TRUST_STORE", "y")
    monkeypatch.setenv("VULTR_CA_BUNDLE", "C:\\trust\\bundle.pem")

    settings = load_settings_from_env()

    assert settings.vultr_api_key == "process-key"
    assert settings.vultr_inference_base_url == "https://example.test/v1"
    assert settings.vultr_chat_model == "example/model"
    assert settings.tosco_fallback is False
    assert settings.tosco_use_system_trust_store is True
    assert settings.vultr_ca_bundle == "C:\\trust\\bundle.pem"


def test_load_settings_from_env_reads_nearest_dotenv_when_enabled(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("TOSCO_LOAD_DOTENV", raising=False)
    monkeypatch.delenv("VULTR_API_KEY", raising=False)
    monkeypatch.delenv("VULTR_INFERENCE_URL", raising=False)
    monkeypatch.delenv("VULTR_INFERENCE_BASE_URL", raising=False)
    monkeypatch.delenv("VULTR_MODEL", raising=False)
    monkeypatch.delenv("VULTR_CHAT_MODEL", raising=False)
    monkeypatch.delenv("TOSCO_FALLBACK", raising=False)
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "VULTR_API_KEY=dotenv-key",
                "VULTR_INFERENCE_URL=https://dotenv.example/v1/chat/completions",
                "VULTR_MODEL=dotenv/model",
                "TOSCO_FALLBACK=false",
                "TOSCO_USE_SYSTEM_TRUST_STORE=no",
                "VULTR_CA_BUNDLE=C:\\dotenv\\bundle.pem",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings_from_env()

    assert settings.vultr_api_key == "dotenv-key"
    assert settings.vultr_inference_base_url == "https://dotenv.example/v1"
    assert settings.vultr_chat_model == "dotenv/model"
    assert settings.tosco_fallback is False
    assert settings.tosco_use_system_trust_store is False
    assert settings.vultr_ca_bundle == "C:\\dotenv\\bundle.pem"
