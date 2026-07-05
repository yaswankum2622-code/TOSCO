"""Issue and verify deterministic clearance tokens for sandbox execution."""

from __future__ import annotations

import hmac
import json
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, ValidationInfo, field_validator

from app.engine.ledger import LedgerEntry
from app.engine.pipeline import ClearanceOutcome
from app.engine.proof import ProofPacket
from app.models import Decision, RunContext, canonical_json_hash


_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")
_LOWER_HEX_RE = re.compile(r"^[0-9a-f]+$")


def _require_non_empty(value: str, field_name: str) -> str:
    """Reject blank token fields that weaken enforcement guarantees."""

    trimmed = value.strip()
    if not trimmed:
        raise ValueError(f"{field_name} cannot be empty")
    return trimmed


def _require_sha256_hex(value: str, field_name: str) -> str:
    """Reject values that are not lowercase SHA-256 hex digests."""

    if _SHA256_HEX_RE.fullmatch(value) is None:
        raise ValueError(f"{field_name} must be a 64-character lowercase hex SHA-256 string")
    return value


class TokenError(RuntimeError):
    """Signal token issuance or verification failures caused by invalid state or config."""


class ClearanceToken(BaseModel):
    """Represent a signed execution permission for one cleared payment action."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    token_version: str = "1.0"
    token_id: str
    run_id: str
    workflow_id: str
    decision: Decision
    vendor_id: str
    amount: float
    currency: str
    bank_account_last4: str
    packet_hash: str
    ledger_entry_hash: str
    issued_at: str
    expires_at: str
    signature: str

    @field_validator(
        "token_version",
        "token_id",
        "run_id",
        "workflow_id",
        "vendor_id",
        "issued_at",
        "expires_at",
    )
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank token identity fields."""

        return _require_non_empty(value, info.field_name)

    @field_validator("decision")
    @classmethod
    def validate_decision(cls, value: Decision) -> Decision:
        """Reject tokens that attempt to authorize anything other than ALLOW."""

        if value is not Decision.ALLOW:
            raise ValueError("decision must be ALLOW")
        return value

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: float) -> float:
        """Reject non-positive cleared amounts."""

        if value <= 0:
            raise ValueError("amount must be > 0")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        """Normalize currency codes to uppercase."""

        return _require_non_empty(value, "currency").upper()

    @field_validator("bank_account_last4")
    @classmethod
    def validate_bank_account_last4(cls, value: str) -> str:
        """Require exactly four numeric characters for the bound account suffix."""

        trimmed = _require_non_empty(value, "bank_account_last4")
        if re.fullmatch(r"\d{4}", trimmed) is None:
            raise ValueError("bank_account_last4 must be exactly 4 numeric chars")
        return trimmed

    @field_validator("packet_hash", "ledger_entry_hash")
    @classmethod
    def validate_sha256_hashes(cls, value: str, info: ValidationInfo) -> str:
        """Require SHA-256 hex digests for proof linkage fields."""

        return _require_sha256_hex(value, info.field_name)

    @field_validator("signature")
    @classmethod
    def validate_signature(cls, value: str) -> str:
        """Require lowercase hex for the HMAC signature."""

        trimmed = _require_non_empty(value, "signature")
        if _LOWER_HEX_RE.fullmatch(trimmed) is None:
            raise ValueError("signature must be lowercase hex")
        return trimmed


class TokenVerificationResult(BaseModel):
    """Describe whether a token or token-bound payment check passed."""

    model_config = ConfigDict(extra="forbid")

    valid: bool
    reason_code: str
    human_reason: str
    token_id: str | None = None


def _deterministic_token_id(run_id: str, packet_hash: str, ledger_entry_hash: str) -> str:
    """Bind the token ID to the exact proof and ledger position it authorizes."""

    return canonical_json_hash(
        {
            "run_id": run_id,
            "packet_hash": packet_hash,
            "ledger_entry_hash": ledger_entry_hash,
        }
    )[:24]


def _token_payload(token: ClearanceToken | dict[str, Any]) -> dict[str, Any]:
    """Return the signed token payload without the signature field."""

    if isinstance(token, ClearanceToken):
        return token.model_dump(mode="json", exclude={"signature"})

    payload = dict(token)
    payload.pop("signature", None)
    return payload


def sign_token_payload(payload: dict[str, Any], secret: str) -> str:
    """Sign execution-critical token fields with HMAC-SHA256."""

    if not secret:
        raise TokenError("secret cannot be empty")

    canonical_payload = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")
    return hmac.new(secret.encode("utf-8"), canonical_payload, "sha256").hexdigest()


def issue_clearance_token(
    *,
    ctx: RunContext,
    outcome: ClearanceOutcome,
    packet: ProofPacket,
    ledger_entry: LedgerEntry,
    secret: str,
    issued_at: str,
    expires_at: str,
) -> ClearanceToken:
    """Issue a signed clearance token only for an ALLOW outcome that matches the proof chain."""

    if not secret:
        raise TokenError("secret cannot be empty")
    if packet.final_decision is not Decision.ALLOW or packet.allow_execution is not True:
        raise TokenError("clearance tokens may only be issued for ALLOW proof packets")
    if packet.human_review is None and (
        outcome.final_decision is not Decision.ALLOW or outcome.allow_execution is not True
    ):
        raise TokenError("clearance tokens may only be issued for ALLOW outcomes")
    if packet.run_id != ctx.run_id:
        raise TokenError("ProofPacket run_id does not match RunContext")
    if packet.workflow_id != ctx.workflow_id:
        raise TokenError("ProofPacket workflow_id does not match RunContext")
    if ledger_entry.run_id != ctx.run_id:
        raise TokenError("LedgerEntry run_id does not match RunContext")

    packet_hash = packet.proof_hash()
    if ledger_entry.packet_hash != packet_hash:
        raise TokenError("LedgerEntry packet_hash does not match ProofPacket proof_hash")

    payload = {
        "token_version": "1.0",
        "token_id": _deterministic_token_id(ctx.run_id, packet_hash, ledger_entry.entry_hash),
        "run_id": ctx.run_id,
        "workflow_id": ctx.workflow_id,
        "decision": Decision.ALLOW.value,
        "vendor_id": ctx.intent.action.vendor_id,
        "amount": ctx.intent.action.amount,
        "currency": ctx.intent.action.currency,
        "bank_account_last4": ctx.intent.action.bank_account_last4,
        "packet_hash": packet_hash,
        "ledger_entry_hash": ledger_entry.entry_hash,
        "issued_at": issued_at,
        "expires_at": expires_at,
    }
    signature = sign_token_payload(payload, secret)

    try:
        return ClearanceToken(**payload, signature=signature)
    except ValidationError as exc:
        raise TokenError(f"Clearance token validation failed: {exc}") from exc


def verify_clearance_token(
    token: ClearanceToken,
    *,
    secret: str,
    now: str,
    expected_packet_hash: str | None = None,
    expected_ledger_entry_hash: str | None = None,
) -> TokenVerificationResult:
    """Verify token signature, expiry, and proof-chain linkage for execution enforcement."""

    if not secret:
        raise TokenError("secret cannot be empty")

    expected_signature = sign_token_payload(_token_payload(token), secret)
    if not hmac.compare_digest(token.signature, expected_signature):
        return TokenVerificationResult(
            valid=False,
            reason_code="SIGNATURE_MISMATCH",
            human_reason="The clearance token signature did not verify.",
            token_id=token.token_id,
        )

    if token.decision is not Decision.ALLOW:
        return TokenVerificationResult(
            valid=False,
            reason_code="TOKEN_DECISION_NOT_ALLOW",
            human_reason="The clearance token does not authorize execution because its decision is not ALLOW.",
            token_id=token.token_id,
        )

    if now > token.expires_at:
        return TokenVerificationResult(
            valid=False,
            reason_code="TOKEN_EXPIRED",
            human_reason="The clearance token has expired.",
            token_id=token.token_id,
        )

    if expected_packet_hash is not None and token.packet_hash != expected_packet_hash:
        return TokenVerificationResult(
            valid=False,
            reason_code="PACKET_HASH_MISMATCH",
            human_reason="The clearance token does not match the expected proof packet hash.",
            token_id=token.token_id,
        )

    if expected_ledger_entry_hash is not None and token.ledger_entry_hash != expected_ledger_entry_hash:
        return TokenVerificationResult(
            valid=False,
            reason_code="LEDGER_HASH_MISMATCH",
            human_reason="The clearance token does not match the expected ledger entry hash.",
            token_id=token.token_id,
        )

    return TokenVerificationResult(
        valid=True,
        reason_code="TOKEN_VALID",
        human_reason="The clearance token signature and proof linkage verified successfully.",
        token_id=token.token_id,
    )


def token_matches_payment(
    token: ClearanceToken,
    *,
    vendor_id: str,
    amount: float,
    currency: str,
    bank_account_last4: str,
) -> TokenVerificationResult:
    """Check that the payment request exactly matches the token-bound cleared action."""

    normalized_currency = currency.upper()
    if token.vendor_id != vendor_id:
        return TokenVerificationResult(
            valid=False,
            reason_code="VENDOR_MISMATCH",
            human_reason="The clearance token vendor does not match the payment request.",
            token_id=token.token_id,
        )
    if token.amount != amount:
        return TokenVerificationResult(
            valid=False,
            reason_code="AMOUNT_MISMATCH",
            human_reason="The clearance token amount does not match the payment request.",
            token_id=token.token_id,
        )
    if token.currency != normalized_currency:
        return TokenVerificationResult(
            valid=False,
            reason_code="CURRENCY_MISMATCH",
            human_reason="The clearance token currency does not match the payment request.",
            token_id=token.token_id,
        )
    if token.bank_account_last4 != bank_account_last4:
        return TokenVerificationResult(
            valid=False,
            reason_code="BANK_ACCOUNT_MISMATCH",
            human_reason="The clearance token bank account does not match the payment request.",
            token_id=token.token_id,
        )

    return TokenVerificationResult(
        valid=True,
        reason_code="PAYMENT_MATCHED",
        human_reason="The clearance token exactly matches the payment request.",
        token_id=token.token_id,
    )
