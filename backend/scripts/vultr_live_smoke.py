"""Manual live smoke test for the Vultr Serverless Inference path."""

from __future__ import annotations

import argparse
import json
import sys
import traceback
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[1]
TLS_TROUBLESHOOTING_MESSAGE = """TLS certificate verification failed. Try:
1. pip install --upgrade certifi truststore
2. Set TOSCO_USE_SYSTEM_TRUST_STORE=true
3. If behind corporate/antivirus TLS inspection, set VULTR_CA_BUNDLE to a PEM bundle containing the trusted root CA.
Never use verify""" + "=False."

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.config import load_settings_from_env
from app.integrations.vultr import (
    VultrInferenceClient,
    VultrIntegrationError,
    VultrSettings,
    extract_json_object,
)
from app.models import Decision
from app.orchestrator.runner import OrchestratorConfig, run_scenario


DIRECT_CHAT_PROMPT = 'Return exactly this JSON object with no markdown: {"status":"ok","provider":"vultr"}'
EXTRACTION_EVIDENCE = {
    "invoice": {
        "invoice_id": "INV-2026-1048",
        "vendor_name": "ACME Industrial Supplies",
        "amount": 340000,
        "bank_account_last4": "8821",
    },
    "vendor_master": {
        "vendor_id": "VEND-ACME-001",
        "registered_bank_last4": "8821",
    },
}
REQUIRED_FIELDS = [
    "invoice_id",
    "vendor_name",
    "amount",
    "bank_account_last4",
]


class SmokeTestError(RuntimeError):
    """Carry a sanitized live-smoke failure payload."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str | None = None,
        error_message: str | None = None,
        response_shape: dict[str, Any] | None = None,
        exit_code: int = 1,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.error_message = error_message
        self.response_shape = response_shape
        self.exit_code = exit_code


def _assert_or_raise(
    condition: bool,
    message: str,
    *,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    """Raise a safe error when a live smoke-test assertion fails."""

    if not condition:
        raise SmokeTestError(
            message,
            error_code=error_code,
            error_message=error_message,
        )


def _short_hash(value: str | None) -> str | None:
    """Show only a short stable prefix for hashes in manual smoke output."""

    if value is None:
        return None
    return value[:12]


def _safe_config(settings: Any) -> dict[str, Any]:
    """Return only non-secret Vultr config fields for printing."""

    return {
        "key_present": bool(settings.vultr_api_key),
        "base_url": settings.vultr_inference_base_url,
        "model": settings.vultr_chat_model,
        "use_system_trust_store": settings.tosco_use_system_trust_store,
        "ca_bundle_present": settings.vultr_ca_bundle is not None,
    }


def _build_client() -> VultrInferenceClient:
    """Create a Vultr client from local settings without printing secrets."""

    settings = load_settings_from_env()
    if not settings.vultr_api_key:
        raise SmokeTestError(
            "VULTR_API_KEY is not set. Create local .env or set it only in this terminal session.",
            exit_code=2,
        )

    print(json.dumps(_safe_config(settings), sort_keys=True))

    try:
        return VultrInferenceClient(
            VultrSettings(
                api_key=settings.vultr_api_key,
                base_url=settings.vultr_inference_base_url,
                chat_model=settings.vultr_chat_model,
                fallback_enabled=settings.tosco_fallback,
                use_system_trust_store=settings.tosco_use_system_trust_store,
                ca_bundle=settings.vultr_ca_bundle,
            )
        )
    except VultrIntegrationError as exc:
        raise SmokeTestError(
            "Vultr TLS configuration is invalid.",
            error_code="VULTR_TLS_CONFIG_ERROR",
            error_message=str(exc),
        ) from exc


def _run_level_one(client: VultrInferenceClient) -> None:
    """Verify a real direct Vultr chat completion can round-trip strict JSON."""

    result = client.chat_completion(
        system_prompt="Return strict JSON only.",
        user_prompt=DIRECT_CHAT_PROMPT,
        temperature=0.0,
        max_tokens=80,
    )
    if not result.ok or result.content is None:
        raise SmokeTestError(
            "Level 1 direct Vultr chat completion failed.",
            error_code=result.error_code,
            error_message=result.error_message,
            response_shape=result.response_shape_summary,
        )

    try:
        payload = extract_json_object(result.content)
    except Exception as exc:
        raise SmokeTestError(
            "Level 1 direct Vultr chat completion returned invalid JSON.",
            error_code="VULTR_JSON_PARSE_ERROR",
            error_message=str(exc),
        ) from exc

    _assert_or_raise(
        payload.get("status") == "ok" and payload.get("provider") == "vultr",
        "Level 1 direct Vultr chat completion returned the wrong JSON payload.",
        error_code="VULTR_BAD_RESPONSE",
        error_message="Expected status=ok and provider=vultr.",
    )
    print("[PASS] Level 1 direct Vultr chat completion worked")


def _run_level_two(client: VultrInferenceClient) -> None:
    """Verify the extraction adapter returns structured fields and source spans."""

    result = client.extract_vendor_payment_fields(
        evidence=EXTRACTION_EVIDENCE,
        required_fields=REQUIRED_FIELDS,
    )
    _assert_or_raise(
        result.ok,
        "Level 2 Vultr extraction adapter failed.",
        error_code=result.error_code,
        error_message=result.error_message,
    )

    for field_name in REQUIRED_FIELDS:
        _assert_or_raise(
            field_name in result.fields and result.fields[field_name] is not None,
            f"Level 2 extraction is missing '{field_name}'.",
            error_code="VULTR_EXTRACTION_INVALID",
            error_message=f"Missing required field '{field_name}'.",
        )
        spans = result.source_spans.get(field_name)
        _assert_or_raise(
            isinstance(spans, list) and len(spans) > 0,
            f"Level 2 extraction is missing source spans for '{field_name}'.",
            error_code="VULTR_EXTRACTION_INVALID",
            error_message=f"Missing source spans for '{field_name}'.",
        )

    print("[PASS] Level 2 Vultr extraction adapter returned valid structured fields")


def _run_level_three(client: VultrInferenceClient) -> None:
    """Verify the orchestrator uses real Vultr extraction but keeps final gating deterministic."""

    run = run_scenario(
        "clean",
        config=OrchestratorConfig(
            use_vultr=True,
            vultr_fallback_enabled=False,
        ),
        vultr_client=client,
    )
    vultr_events = [event for event in run.timeline.event_types if event.startswith("VULTR_")]

    _assert_or_raise(
        run.final_decision is Decision.ALLOW,
        "Level 3 orchestrator run did not finish with ALLOW.",
        error_code="ORCHESTRATOR_DECISION_UNEXPECTED",
        error_message=f"Expected ALLOW, got {run.final_decision.value}.",
    )
    _assert_or_raise(
        run.allow_execution,
        "Level 3 orchestrator run did not allow execution.",
        error_code="ORCHESTRATOR_EXECUTION_BLOCKED",
        error_message="Expected allow_execution to be true.",
    )
    _assert_or_raise(
        run.clearance_token is not None,
        "Level 3 orchestrator run did not issue a clearance token.",
        error_code="CLEARANCE_TOKEN_MISSING",
        error_message="Expected a clearance token for the clean run.",
    )
    _assert_or_raise(
        run.execution_result.accepted,
        "Level 3 Mock Bank did not accept the cleared payment.",
        error_code="MOCK_BANK_REJECTED",
        error_message=run.execution_result.human_reason,
    )
    _assert_or_raise(
        "VULTR_EXTRACTION_STARTED" in vultr_events,
        "Level 3 timeline is missing VULTR_EXTRACTION_STARTED.",
        error_code="TIMELINE_EVENT_MISSING",
        error_message="Missing VULTR_EXTRACTION_STARTED.",
    )
    _assert_or_raise(
        "VULTR_EXTRACTION_SUCCEEDED" in vultr_events,
        "Level 3 timeline is missing VULTR_EXTRACTION_SUCCEEDED.",
        error_code="TIMELINE_EVENT_MISSING",
        error_message="Missing VULTR_EXTRACTION_SUCCEEDED.",
    )
    _assert_or_raise(
        "VULTR_EXTRACTION_FALLBACK" not in vultr_events,
        "Level 3 timeline unexpectedly used Vultr fallback.",
        error_code="VULTR_FALLBACK_USED",
        error_message="Fallback must remain disabled for the live smoke test.",
    )

    print(
        "[PASS] Level 3 TOSCO orchestrator used real Vultr extraction and deterministic clearance succeeded"
    )
    print(
        json.dumps(
            {
                "run_id": run.run_context.run_id,
                "final_decision": run.final_decision.value,
                "token_issued": run.clearance_token is not None,
                "mock_bank_status": run.execution_result.status,
                "proof_hash": _short_hash(run.proof_packet.proof_hash()),
                "ledger_entry_hash": _short_hash(run.ledger_entry.entry_hash),
                "vultr_events": vultr_events,
            },
            sort_keys=True,
        )
    )


def _print_failure(error: SmokeTestError, *, show_response_shape: bool = False) -> None:
    """Print only sanitized failure metadata for the live smoke script."""

    if error.error_code == "VULTR_BAD_RESPONSE":
        print("Vultr responded, but adapter could not parse assistant content.")
    if error.error_code is not None or error.error_message is not None:
        print(
            json.dumps(
                {
                    "error_code": error.error_code,
                    "error_message": error.error_message,
                },
                sort_keys=True,
            )
        )
    print(f"[FAIL] {error}")
    if error.error_code == "VULTR_TLS_VERIFY_FAILED":
        print(TLS_TROUBLESHOOTING_MESSAGE)
    if error.error_code in {"VULTR_JSON_PARSE_ERROR", "VULTR_EXTRACTION_INVALID"} and not show_response_shape:
        print("Try: python scripts\\vultr_live_smoke.py --show-response-shape")
    if show_response_shape and error.error_code == "VULTR_BAD_RESPONSE":
        if error.response_shape is not None:
            print(json.dumps(error.response_shape, sort_keys=True))
        else:
            print("No safe response-shape summary was available.")


def main(argv: list[str] | None = None) -> int:
    """Run the live Vultr smoke test and return a process exit code."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--debug", action="store_true", help="Print a traceback on failure.")
    parser.add_argument(
        "--show-response-shape",
        action="store_true",
        help="Print safe response-shape diagnostics when the adapter cannot parse content.",
    )
    args = parser.parse_args(argv)

    try:
        client = _build_client()
        _run_level_one(client)
        _run_level_two(client)
        _run_level_three(client)
    except SmokeTestError as exc:
        if exc.exit_code == 2:
            print(str(exc))
            return exc.exit_code
        _print_failure(exc, show_response_shape=args.show_response_shape)
        if args.debug:
            traceback.print_exc()
        return exc.exit_code
    except Exception:
        print("[FAIL] Live Vultr smoke test failed due to an unexpected error.")
        if args.debug:
            traceback.print_exc()
        return 1

    print("LIVE VULTR SMOKE TEST PASSED")
    print("Real Serverless Inference path confirmed.")
    print("Vultr extracted. TOSCO deterministic gates decided. Mock Bank obeyed clearance token.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
