"""Build deterministic custom-run seeds from judge-supplied payment input."""

from __future__ import annotations

import re
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator

from app.agent.reference_ap_agent import AgentProposal
from app.models import Decision, ProposedAction
from app.scenarios.loader import ScenarioSeed, _evidence_refs

_INJECTION_PATTERN = re.compile(
    r"ignore|reroute|pay to|approve immediately|bank.*\d{4}",
    re.IGNORECASE,
)

_MAX_VENDOR_ID_LEN = 64
_MAX_INVOICE_TEXT_LEN = 4000
_MIN_AMOUNT = 0.01
_MAX_AMOUNT = 50_000_000.0


def _require_non_empty(value: str, field_name: str) -> str:
    trimmed = value.strip()
    if not trimmed:
        raise ValueError(f"{field_name} cannot be empty")
    return trimmed


def _validate_bank_last4(value: str, field_name: str) -> str:
    trimmed = _require_non_empty(value, field_name)
    if re.fullmatch(r"\d{4}", trimmed) is None:
        raise ValueError(f"{field_name} must be exactly 4 numeric characters")
    return trimmed


class CustomRunInput(BaseModel):
    """Validated judge input for a live custom clearance run."""

    model_config = ConfigDict(extra="forbid")

    vendor_id: str
    amount: float
    currency: str = "USD"
    bank_account_last4: str
    registered_bank_last4: str
    invoice_text: str
    bank_owner_matches_vendor: bool
    request_domain_age_days: int
    logistics_confirmed: bool
    is_first_payment_to_account: bool
    use_vultr: bool = False

    @field_validator("vendor_id")
    @classmethod
    def validate_vendor_id(cls, value: str) -> str:
        trimmed = _require_non_empty(value, "vendor_id")
        if len(trimmed) > _MAX_VENDOR_ID_LEN:
            raise ValueError(f"vendor_id must be at most {_MAX_VENDOR_ID_LEN} characters")
        return trimmed

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, value: float) -> float:
        if not _MIN_AMOUNT <= value <= _MAX_AMOUNT:
            raise ValueError(f"amount must be between {_MIN_AMOUNT} and {_MAX_AMOUNT}")
        return value

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        trimmed = _require_non_empty(value, "currency").upper()
        if len(trimmed) != 3 or not trimmed.isalpha():
            raise ValueError("currency must be a 3-letter ISO code")
        return trimmed

    @field_validator("bank_account_last4")
    @classmethod
    def validate_bank_account_last4(cls, value: str) -> str:
        return _validate_bank_last4(value, "bank_account_last4")

    @field_validator("registered_bank_last4")
    @classmethod
    def validate_registered_bank_last4(cls, value: str) -> str:
        return _validate_bank_last4(value, "registered_bank_last4")

    @field_validator("invoice_text")
    @classmethod
    def validate_invoice_text(cls, value: str) -> str:
        trimmed = value.strip()
        if not trimmed:
            raise ValueError("invoice_text cannot be empty")
        if len(trimmed) > _MAX_INVOICE_TEXT_LEN:
            raise ValueError(f"invoice_text must be at most {_MAX_INVOICE_TEXT_LEN} characters")
        return trimmed

    @field_validator("request_domain_age_days")
    @classmethod
    def validate_request_domain_age_days(cls, value: int) -> int:
        if value < 0 or value > 100_000:
            raise ValueError("request_domain_age_days must be between 0 and 100000")
        return value


def detect_injection_marker(
    invoice_text: str,
    bank_account_last4: str,
    registered_bank_last4: str,
) -> bool:
    """Detect typed injection routing when invoice prose diverges from vendor master."""

    if bank_account_last4 == registered_bank_last4:
        return False
    return _INJECTION_PATTERN.search(invoice_text) is not None


def build_custom_seed(payload: CustomRunInput) -> ScenarioSeed:
    """Materialize a ScenarioSeed from judge input without changing gate logic."""

    run_suffix = uuid.uuid4().hex[:8]
    run_id = f"run-custom-{run_suffix}"
    intent_id = f"intent-custom-{run_suffix}"
    invoice_id = f"INV-CUSTOM-{run_suffix.upper()}"

    injection_marker = detect_injection_marker(
        payload.invoice_text,
        payload.bank_account_last4,
        payload.registered_bank_last4,
    )

    evidence: dict[str, Any] = {
        "invoice": {
            "doc_id": f"invoice-custom-{run_suffix}",
            "invoice_id": invoice_id,
            "vendor_name": payload.vendor_id,
            "amount": payload.amount,
            "currency": payload.currency,
            "bank_account_last4": payload.bank_account_last4,
            "body": payload.invoice_text,
        },
        "po": {
            "doc_id": f"po-custom-{run_suffix}",
            "po_id": f"PO-CUSTOM-{run_suffix.upper()}",
            "vendor_id": payload.vendor_id,
            "amount": payload.amount,
        },
        "grn": {
            "doc_id": f"grn-custom-{run_suffix}",
            "grn_id": f"GRN-CUSTOM-{run_suffix.upper()}",
            "delivery_confirmed": True,
        },
        "vendor_master": {
            "doc_id": f"vendor-master-custom-{run_suffix}",
            "vendor_id": payload.vendor_id,
            "vendor_name": payload.vendor_id,
            "registered_bank_last4": payload.registered_bank_last4,
        },
        "policy_pack": {
            "doc_id": "policy-pack-v1",
            "policy_name": "Vendor Payment Control Pack",
            "requires_reality_gate_for_high_value": True,
        },
    }

    extraction_fields = {
        "invoice_id": invoice_id,
        "vendor_name": payload.vendor_id,
        "amount": payload.amount,
        "bank_account_last4": payload.bank_account_last4,
    }
    source_spans = {field_name: [0, 1] for field_name in extraction_fields}

    signals = {
        "duplicate_invoice": False,
        "injection_marker_detected": injection_marker,
        "bank_changed_days_ago": None,
        "is_first_payment_to_account": payload.is_first_payment_to_account,
        "velocity_risk": False,
        "sod_violation": False,
        "human_confirmed": True,
        "bank_owner_matches_vendor": payload.bank_owner_matches_vendor,
        "request_domain_age_days": payload.request_domain_age_days,
        "logistics_confirmed": payload.logistics_confirmed,
    }

    proposed_action = ProposedAction(
        type="payment",
        vendor_id=payload.vendor_id,
        amount=payload.amount,
        currency=payload.currency,
        bank_account_last4=payload.bank_account_last4,
    )

    return ScenarioSeed(
        scenario="custom",
        title="Custom Judge Payment",
        description="A judge-supplied vendor payment run through the full clearance pipeline.",
        agent_behavior="The reference AP agent proposes payment from the submitted invoice.",
        run_id=run_id,
        intent_id=intent_id,
        proposed_action=proposed_action,
        evidence=evidence,
        extraction_fields=extraction_fields,
        source_spans=source_spans,
        signals=signals,
        expected_naive_agent_action="approve_payment",
        expected_tosco_decision=Decision.ALLOW,
    )


def build_custom_proposal(seed: ScenarioSeed) -> AgentProposal:
    """Build the naive agent proposal for a custom seed."""

    from app.models import ActionIntent

    intent = ActionIntent(
        intent_id=seed.intent_id,
        agent_id=seed.agent_id,
        workflow=seed.workflow_id,
        action=seed.proposed_action,
        evidence_refs=_evidence_refs(seed.evidence),
        declared_confidence=0.94,
        requested_mode="assisted",
    )
    return AgentProposal(
        scenario=seed.scenario,
        intent=intent,
        naive_action=seed.expected_naive_agent_action,
        proposed_reason=(
            "The reference AP agent proposes payment from the judge-supplied invoice and evidence."
        ),
    )
