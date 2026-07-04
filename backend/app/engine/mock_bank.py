"""Enforce TOSCO clearance tokens at the sandbox execution boundary."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

from app.engine.token import (
    ClearanceToken,
    TokenError,
    token_matches_payment,
    verify_clearance_token,
)
from app.models import RunContext, canonical_json_hash


def _require_non_empty(value: str, field_name: str) -> str:
    """Reject blank payment request fields that weaken enforcement checks."""

    trimmed = value.strip()
    if not trimmed:
        raise ValueError(f"{field_name} cannot be empty")
    return trimmed


class MockBankError(RuntimeError):
    """Signal configuration or programmer errors in the Mock Bank adapter."""


class PaymentExecutionRequest(BaseModel):
    """Describe the exact payment the Mock Bank is being asked to execute."""

    model_config = ConfigDict(extra="forbid")

    run_id: str
    vendor_id: str
    amount: float
    currency: str
    bank_account_last4: str
    token_id: str | None = None

    @field_validator("run_id", "vendor_id")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank payment request identifiers."""

        return _require_non_empty(value, info.field_name)

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: float) -> float:
        """Reject non-positive execution amounts."""

        if value <= 0:
            raise ValueError("amount must be > 0")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        """Normalize currency codes to uppercase for exact-match checks."""

        return _require_non_empty(value, "currency").upper()

    @field_validator("bank_account_last4")
    @classmethod
    def validate_bank_account_last4(cls, value: str) -> str:
        """Require exactly four numeric characters for bank account suffixes."""

        trimmed = _require_non_empty(value, "bank_account_last4")
        if len(trimmed) != 4 or not trimmed.isdigit():
            raise ValueError("bank_account_last4 must be exactly 4 numeric chars")
        return trimmed


class MockBankExecutionResult(BaseModel):
    """Describe whether the Mock Bank accepted or rejected a payment request."""

    model_config = ConfigDict(extra="forbid")

    accepted: bool
    status: str
    reason_code: str
    human_reason: str
    run_id: str
    token_id: str | None = None
    execution_reference: str | None = None


def build_payment_request_from_context(
    ctx: RunContext,
    token: ClearanceToken | None = None,
) -> PaymentExecutionRequest:
    """Construct a payment request from the proposed action and optional token."""

    action = ctx.intent.action
    return PaymentExecutionRequest(
        run_id=ctx.run_id,
        vendor_id=action.vendor_id,
        amount=action.amount,
        currency=action.currency,
        bank_account_last4=action.bank_account_last4,
        token_id=token.token_id if token is not None else None,
    )


def _reject(
    request: PaymentExecutionRequest,
    *,
    reason_code: str,
    human_reason: str,
    token_id: str | None,
) -> MockBankExecutionResult:
    """Create a standardized rejection result for sandbox execution."""

    return MockBankExecutionResult(
        accepted=False,
        status="REJECTED",
        reason_code=reason_code,
        human_reason=human_reason,
        run_id=request.run_id,
        token_id=token_id,
        execution_reference=None,
    )


def attempt_mock_bank_execution(
    request: PaymentExecutionRequest,
    *,
    token: ClearanceToken | None,
    secret: str,
    now: str,
    expected_packet_hash: str,
    expected_ledger_entry_hash: str,
) -> MockBankExecutionResult:
    """Accept only requests backed by a valid TOSCO clearance token."""

    if not secret:
        raise MockBankError("secret cannot be empty")

    if token is None:
        return _reject(
            request,
            reason_code="MISSING_CLEARANCE_TOKEN",
            human_reason="Mock Bank rejected the payment because no TOSCO clearance token was provided.",
            token_id=None,
        )

    try:
        token_verification = verify_clearance_token(
            token,
            secret=secret,
            now=now,
            expected_packet_hash=expected_packet_hash,
            expected_ledger_entry_hash=expected_ledger_entry_hash,
        )
    except TokenError as exc:
        raise MockBankError(f"Mock Bank token verification failed: {exc}") from exc

    if not token_verification.valid:
        return _reject(
            request,
            reason_code=token_verification.reason_code,
            human_reason=token_verification.human_reason,
            token_id=token.token_id,
        )

    payment_match = token_matches_payment(
        token,
        vendor_id=request.vendor_id,
        amount=request.amount,
        currency=request.currency,
        bank_account_last4=request.bank_account_last4,
    )
    if not payment_match.valid:
        return _reject(
            request,
            reason_code=payment_match.reason_code,
            human_reason=payment_match.human_reason,
            token_id=token.token_id,
        )

    if token.run_id != request.run_id:
        return _reject(
            request,
            reason_code="RUN_ID_MISMATCH",
            human_reason="Mock Bank rejected the payment because the clearance token run_id did not match the payment request.",
            token_id=token.token_id,
        )

    execution_reference = "MOCKBANK-" + canonical_json_hash(
        {"run_id": request.run_id, "token_id": token.token_id}
    )[:16]
    return MockBankExecutionResult(
        accepted=True,
        status="ACCEPTED",
        reason_code="EXECUTION_ACCEPTED",
        human_reason="Mock Bank accepted the payment because a valid TOSCO clearance token matched the payment request.",
        run_id=request.run_id,
        token_id=token.token_id,
        execution_reference=execution_reference,
    )
