from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.models import (
    ActionIntent,
    Decision,
    DecisionPolicy,
    GateResult,
    GateStatus,
    ProposedAction,
    RunContext,
    SealedExtraction,
    ToolCall,
    WorkflowDefinition,
    more_severe,
)


def build_action() -> ProposedAction:
    return ProposedAction(
        vendor_id="V-1042",
        amount=340000,
        currency="usd",
        bank_account_last4="8821",
    )


def build_intent() -> ActionIntent:
    return ActionIntent(
        intent_id="intent-001",
        agent_id="ap-agent-01",
        action=build_action(),
        evidence_refs=["invoice-2291"],
        declared_confidence=0.94,
    )


def build_workflow() -> WorkflowDefinition:
    return WorkflowDefinition(
        workflow_id="vendor_payment",
        workflow_name="AI Vendor Payment & Bank-Change Clearance",
        required_evidence_types=["invoice", "po", "grn", "vendor_master", "policy_pack"],
        extraction_schema={
            "required_fields": ["invoice_id", "vendor_name", "amount", "bank_account_last4"]
        },
        gates_to_run=["G1_EVIDENCE", "G2_GROUNDEDNESS", "G3_POLICY", "G4_RISK", "G5_REALITY"],
        tools_to_call=[
            "policy_tool",
            "risk_tool",
            "bank_owner_check",
            "domain_age_check",
            "logistics_check",
        ],
        decision_policy=DecisionPolicy(),
        proof_packet_template="vendor_payment_proof",
    )


def test_more_severe_returns_stricter_decision() -> None:
    assert more_severe(Decision.BLOCK, Decision.ALLOW) is Decision.BLOCK
    assert more_severe(Decision.FREEZE, Decision.BLOCK) is Decision.FREEZE
    assert (
        more_severe(Decision.ALLOW, Decision.REQUEST_MORE_EVIDENCE)
        is Decision.REQUEST_MORE_EVIDENCE
    )


def test_proposed_action_validates_happy_path_and_normalizes_currency() -> None:
    action = build_action()

    assert action.type == "payment"
    assert action.currency == "USD"


@pytest.mark.parametrize("amount", [0, -1])
def test_proposed_action_rejects_non_positive_amount(amount: float) -> None:
    with pytest.raises(ValidationError):
        ProposedAction(
            vendor_id="V-1042",
            amount=amount,
            bank_account_last4="8821",
        )


@pytest.mark.parametrize("last4", ["12A4", "123", "12345"])
def test_proposed_action_rejects_bad_bank_account_last4(last4: str) -> None:
    with pytest.raises(ValidationError):
        ProposedAction(
            vendor_id="V-1042",
            amount=10,
            bank_account_last4=last4,
        )


def test_action_intent_validates_vendor_payment_proposal() -> None:
    intent = build_intent()

    assert intent.workflow == "vendor_payment"
    assert intent.declared_confidence == pytest.approx(0.94)


@pytest.mark.parametrize("confidence", [-0.1, 1.1])
def test_action_intent_rejects_confidence_outside_range(confidence: float) -> None:
    with pytest.raises(ValidationError):
        ActionIntent(
            intent_id="intent-001",
            agent_id="ap-agent-01",
            action=build_action(),
            declared_confidence=confidence,
        )


def test_sealed_extraction_is_frozen_and_hash_is_stable() -> None:
    extraction = SealedExtraction(
        doc_id="invoice-2291",
        fields={"invoice_id": "INV-2291", "amount": 340000},
        source_spans={"invoice_id": [0, 8], "amount": [20, 26]},
        extractor="sandbox-fallback",
    )
    same_extraction = SealedExtraction(
        doc_id="invoice-2291",
        fields={"invoice_id": "INV-2291", "amount": 340000},
        source_spans={"invoice_id": [0, 8], "amount": [20, 26]},
        extractor="sandbox-fallback",
    )
    changed_extraction = SealedExtraction(
        doc_id="invoice-2291",
        fields={"invoice_id": "INV-2291", "amount": 340001},
        source_spans={"invoice_id": [0, 8], "amount": [20, 26]},
        extractor="sandbox-fallback",
    )

    assert extraction.sealed_hash() == same_extraction.sealed_hash()
    assert extraction.sealed_hash() != changed_extraction.sealed_hash()

    with pytest.raises(ValidationError):
        extraction.doc_id = "invoice-2292"  # type: ignore[misc]

    with pytest.raises(TypeError):
        extraction.fields["amount"] = 1


def test_tool_call_rejects_negative_latency() -> None:
    with pytest.raises(ValidationError):
        ToolCall(
            tool_id="risk_tool",
            input={"vendor_id": "V-1042"},
            output={"risk": "low"},
            latency_ms=-1,
        )


def test_gate_result_rejects_empty_reason_code() -> None:
    with pytest.raises(ValidationError):
        GateResult(
            gate_id="G1_EVIDENCE",
            name="Evidence Gate",
            status=GateStatus.FAIL,
            decision=Decision.REQUEST_MORE_EVIDENCE,
            reason_code="",
            human_reason="Missing invoice",
        )


def test_workflow_definition_validates_vendor_payment_shape() -> None:
    workflow = build_workflow()

    assert workflow.workflow_id == "vendor_payment"
    assert workflow.execution_adapter == "sandbox"


def test_workflow_definition_rejects_empty_gates_to_run() -> None:
    with pytest.raises(ValidationError):
        WorkflowDefinition(
            workflow_id="vendor_payment",
            workflow_name="AI Vendor Payment & Bank-Change Clearance",
            required_evidence_types=["invoice"],
            extraction_schema={"required_fields": ["invoice_id"]},
            gates_to_run=[],
            tools_to_call=["policy_tool"],
            decision_policy=DecisionPolicy(),
            proof_packet_template="vendor_payment_proof",
        )


def test_run_context_default_collections_are_not_shared() -> None:
    first = RunContext(run_id="run-001", intent=build_intent(), workflow_id="vendor_payment")
    second = RunContext(run_id="run-002", intent=build_intent(), workflow_id="vendor_payment")

    first.evidence["invoice"] = {"doc_id": "invoice-2291"}
    first.tool_calls.append(
        ToolCall(tool_id="policy_tool", input={"amount": 10}, output={"policy": "ok"})
    )
    first.results.append(
        GateResult(
            gate_id="G1_EVIDENCE",
            name="Evidence Gate",
            status=GateStatus.PASS,
            decision=Decision.ALLOW,
            reason_code="EVIDENCE_OK",
            human_reason="All required evidence is present",
        )
    )

    assert second.evidence == {}
    assert second.tool_calls == []
    assert second.results == []
