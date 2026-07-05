from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


BACKEND_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = BACKEND_ROOT / "scripts" / "vultr_live_smoke.py"


def _run_script_without_key() -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["TOSCO_LOAD_DOTENV"] = "false"
    env["INTENTIONALLY_HIDDEN_SECRET"] = "super-secret-value"
    env.pop("VULTR_API_KEY", None)
    env.pop("VULTR_INFERENCE_BASE_URL", None)
    env.pop("VULTR_CHAT_MODEL", None)
    env.pop("TOSCO_FALLBACK", None)

    return subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=BACKEND_ROOT,
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )


def test_live_smoke_script_exists() -> None:
    assert SCRIPT_PATH.is_file()


def test_live_smoke_script_has_no_real_key_placeholder_value() -> None:
    content = SCRIPT_PATH.read_text(encoding="utf-8")

    assert "PASTE_REAL_KEY" not in content


def test_live_smoke_script_exits_code_2_without_key() -> None:
    completed = _run_script_without_key()
    output = completed.stdout + completed.stderr

    assert completed.returncode == 2
    assert (
        "VULTR_API_KEY is not set. Create local .env or set it only in this terminal session."
        in output
    )


def test_live_smoke_script_missing_key_output_does_not_leak_secret() -> None:
    completed = _run_script_without_key()
    output = completed.stdout + completed.stderr

    assert "super-secret-value" not in output
    assert "Bearer " not in output
