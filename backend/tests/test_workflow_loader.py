from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from app.engine.workflow import (
    WorkflowLoadError,
    get_workflow,
    load_workflow_definition,
    load_workflow_registry,
)


def workflow_payload(
    *,
    workflow_id: str = "vendor_payment",
    workflow_name: str = "AI Vendor Payment & Bank-Change Clearance",
) -> dict[str, object]:
    return {
        "workflow_id": workflow_id,
        "workflow_name": workflow_name,
        "required_evidence_types": [
            "invoice",
            "po",
            "grn",
            "vendor_master",
            "policy_pack",
        ],
        "extraction_schema": {
            "required_fields": [
                "invoice_id",
                "vendor_name",
                "amount",
                "bank_account_last4",
            ],
            "optional_fields": ["payment_terms"],
        },
        "gates_to_run": [
            "G1_EVIDENCE",
            "G2_GROUNDEDNESS",
            "G3_POLICY",
            "G4_RISK",
            "G5_REALITY",
            "G6_DECISION_SEAL",
        ],
        "tools_to_call": [
            "policy_tool",
            "risk_tool",
            "bank_owner_check",
            "domain_age_check",
            "logistics_check",
        ],
        "decision_policy": {
            "allow_requires_all_pass": True,
            "high_value_threshold": 50000,
            "reality_required_above": 50000,
            "mandatory_human_confirm": False,
        },
        "proof_packet_template": "vendor_payment_proof",
        "execution_adapter": "sandbox",
    }


def write_yaml(path: Path, payload: object) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_load_workflow_definition_loads_vendor_payment_yaml() -> None:
    workflow = load_workflow_definition(
        Path(__file__).resolve().parents[1] / "workflows" / "vendor_payment.yaml"
    )

    assert workflow.workflow_id == "vendor_payment"
    assert "Vendor Payment" in workflow.workflow_name
    assert workflow.required_evidence_types == [
        "invoice",
        "po",
        "grn",
        "vendor_master",
        "policy_pack",
    ]
    assert workflow.gates_to_run == [
        "G1_EVIDENCE",
        "G2_GROUNDEDNESS",
        "G3_POLICY",
        "G4_RISK",
        "G5_REALITY",
        "G6_DECISION_SEAL",
    ]
    assert {"bank_owner_check", "domain_age_check", "logistics_check"}.issubset(
        workflow.tools_to_call
    )
    assert workflow.execution_adapter == "sandbox"


def test_loader_rejects_missing_file(tmp_path: Path) -> None:
    missing_path = tmp_path / "missing.yaml"

    with pytest.raises(WorkflowLoadError, match="not found"):
        load_workflow_definition(missing_path)


def test_loader_rejects_invalid_yaml_root(tmp_path: Path) -> None:
    path = tmp_path / "bad.yaml"
    path.write_text("- bad\n- shape\n", encoding="utf-8")

    with pytest.raises(WorkflowLoadError, match="mapping at the root"):
        load_workflow_definition(path)


def test_loader_rejects_unknown_gate_id(tmp_path: Path) -> None:
    path = tmp_path / "unknown_gate.yaml"
    payload = workflow_payload()
    payload["gates_to_run"] = ["G1_EVIDENCE", "G_UNKNOWN"]
    write_yaml(path, payload)

    with pytest.raises(WorkflowLoadError, match="G_UNKNOWN"):
        load_workflow_definition(path)


def test_loader_rejects_duplicate_gate_ids(tmp_path: Path) -> None:
    path = tmp_path / "duplicate_gate.yaml"
    payload = workflow_payload()
    payload["gates_to_run"] = ["G1_EVIDENCE", "G1_EVIDENCE"]
    write_yaml(path, payload)

    with pytest.raises(WorkflowLoadError, match="duplicate gate IDs"):
        load_workflow_definition(path)


def test_load_workflow_registry_loads_multiple_yaml_files(tmp_path: Path) -> None:
    write_yaml(
        tmp_path / "z_vendor_payment.yaml",
        workflow_payload(),
    )
    write_yaml(
        tmp_path / "a_vendor_bank_change.yaml",
        workflow_payload(
            workflow_id="vendor_bank_change",
            workflow_name="AI Vendor Bank Change Clearance",
        ),
    )

    registry = load_workflow_registry(tmp_path)

    assert list(registry) == ["vendor_bank_change", "vendor_payment"]
    assert sorted(registry) == ["vendor_bank_change", "vendor_payment"]
    assert registry["vendor_bank_change"].workflow_name == "AI Vendor Bank Change Clearance"
    assert registry["vendor_payment"].workflow_id == "vendor_payment"


def test_registry_rejects_duplicate_workflow_id(tmp_path: Path) -> None:
    write_yaml(tmp_path / "first.yaml", workflow_payload(workflow_id="duplicate_workflow"))
    write_yaml(
        tmp_path / "second.yaml",
        workflow_payload(
            workflow_id="duplicate_workflow",
            workflow_name="Another Workflow Name",
        ),
    )

    with pytest.raises(WorkflowLoadError, match="first.yaml"):
        load_workflow_registry(tmp_path)


def test_get_workflow_returns_valid_workflow(tmp_path: Path) -> None:
    write_yaml(tmp_path / "vendor_payment.yaml", workflow_payload())
    registry = load_workflow_registry(tmp_path)

    workflow = get_workflow(registry, "vendor_payment")

    assert workflow.workflow_id == "vendor_payment"


def test_get_workflow_rejects_unknown_workflow(tmp_path: Path) -> None:
    write_yaml(tmp_path / "vendor_payment.yaml", workflow_payload())
    registry = load_workflow_registry(tmp_path)

    with pytest.raises(WorkflowLoadError, match="Available workflows: vendor_payment"):
        get_workflow(registry, "missing_workflow")


def test_loader_rejects_empty_required_evidence(tmp_path: Path) -> None:
    path = tmp_path / "missing_evidence.yaml"
    payload = workflow_payload()
    payload["required_evidence_types"] = []
    write_yaml(path, payload)

    with pytest.raises(WorkflowLoadError, match="required_evidence_types"):
        load_workflow_definition(path)


def test_loader_rejects_empty_tools_to_call(tmp_path: Path) -> None:
    path = tmp_path / "missing_tools.yaml"
    payload = workflow_payload()
    payload["tools_to_call"] = []
    write_yaml(path, payload)

    with pytest.raises(WorkflowLoadError, match="tools_to_call"):
        load_workflow_definition(path)
