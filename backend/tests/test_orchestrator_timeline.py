from __future__ import annotations

from pathlib import Path

from app.orchestrator.runner import (
    OrchestratorConfig,
    run_all_demo_scenarios,
    run_scenario,
    summarize_orchestrated_run,
)
from app.scenarios.loader import load_scenario_seed, seed_to_run_context
from app.engine.pipeline import run_clearance
from app.engine.workflow import load_workflow_definition
from app.models import Decision, WorkflowDefinition


def load_workflow() -> WorkflowDefinition:
    return load_workflow_definition(
        Path(__file__).resolve().parents[1] / "workflows" / "vendor_payment.yaml"
    )


def timeline_payloads(run, event_type: str):
    return [event.payload for event in run.timeline.events if event.event_type == event_type]


def first_gate_completed_payload(run, gate_id: str):
    for event in run.timeline.events:
        if event.event_type == "GATE_COMPLETED" and event.payload.get("gate_id") == gate_id:
            return event.payload
    raise AssertionError(f"Missing GATE_COMPLETED event for {gate_id}")


def test_clean_scenario_orchestrates_end_to_end() -> None:
    run = run_scenario("clean")

    assert run.final_decision is Decision.ALLOW
    assert run.allow_execution is True
    assert run.clearance_token is not None
    assert run.execution_result.accepted is True
    assert run.execution_result.reason_code == "EXECUTION_ACCEPTED"
    assert run.proof_packet.proof_hash() == run.ledger_entry.packet_hash
    assert "CLEARANCE_TOKEN_ISSUED" in run.timeline.event_types
    assert "EXECUTION_ACCEPTED" in run.timeline.event_types


def test_injection_scenario_orchestrates_end_to_end() -> None:
    run = run_scenario("injection")

    assert run.final_decision is Decision.BLOCK
    assert run.allow_execution is False
    assert run.clearance_token is None
    assert run.execution_result.accepted is False
    assert run.execution_result.reason_code == "MISSING_CLEARANCE_TOKEN"
    assert "CLEARANCE_TOKEN_SKIPPED" in run.timeline.event_types
    assert "EXECUTION_REJECTED" in run.timeline.event_types
    assert first_gate_completed_payload(run, "G2_GROUNDEDNESS")["reason_code"] == "BANK_ACCOUNT_MISMATCH"


def test_forgery_scenario_orchestrates_end_to_end() -> None:
    run = run_scenario("forgery")

    assert run.final_decision is Decision.FREEZE
    assert run.allow_execution is False
    assert run.clearance_token is None
    assert run.execution_result.accepted is False
    assert run.execution_result.reason_code == "MISSING_CLEARANCE_TOKEN"
    assert "CLEARANCE_TOKEN_SKIPPED" in run.timeline.event_types
    assert "EXECUTION_REJECTED" in run.timeline.event_types
    assert first_gate_completed_payload(run, "G5_REALITY")["reason_code"] == "REALITY_OWNER_MISMATCH_FREEZE"


def test_timeline_indices_are_sequential() -> None:
    run = run_scenario("clean")

    assert [event.index for event in run.timeline.events] == list(range(run.timeline.length))
    assert run.timeline.length == len(run.timeline.events)


def test_timeline_order_is_correct() -> None:
    run = run_scenario("clean")
    event_types = run.timeline.event_types

    assert event_types.index("AGENT_PROPOSED") < event_types.index("PLAN_STARTED")
    assert event_types.index("PLAN_STARTED") < event_types.index("EVIDENCE_RETRIEVED")
    assert event_types.index("EVIDENCE_RETRIEVED") < event_types.index("EXTRACTION_STARTED")
    assert event_types.index("EXTRACTION_SEALED") < event_types.index("GATE_STARTED")
    assert max(i for i, event in enumerate(event_types) if event == "GATE_COMPLETED") < event_types.index("DECISION_MADE")
    assert event_types.index("DECISION_MADE") < event_types.index("PROOF_SEALED")
    assert event_types.index("PROOF_SEALED") < event_types.index("LEDGER_APPENDED")
    token_event_index = event_types.index("CLEARANCE_TOKEN_ISSUED")
    assert event_types.index("LEDGER_APPENDED") < token_event_index
    assert token_event_index < event_types.index("EXECUTION_ATTEMPTED")
    assert event_types.index("EXECUTION_ATTEMPTED") < event_types.index("EXECUTION_ACCEPTED")


def test_each_gate_emits_started_and_completed_events() -> None:
    workflow = load_workflow()
    run = run_scenario("clean")

    assert run.timeline.event_types.count("GATE_STARTED") == len(workflow.gates_to_run)
    assert run.timeline.event_types.count("GATE_COMPLETED") == len(workflow.gates_to_run)


def test_each_workflow_tool_emits_tool_called_event() -> None:
    workflow = load_workflow()
    run = run_scenario("clean")
    tool_payloads = timeline_payloads(run, "TOOL_CALLED")

    assert len(tool_payloads) == len(workflow.tools_to_call)
    assert all(payload["simulated"] is True for payload in tool_payloads)


def test_run_all_demo_scenarios_uses_shared_ledger_chain() -> None:
    runs = run_all_demo_scenarios()

    assert list(runs) == ["clean", "injection", "forgery"]
    assert runs["clean"].ledger_entry.index == 0
    assert runs["injection"].ledger_entry.index == 1
    assert runs["forgery"].ledger_entry.index == 2
    assert runs["injection"].ledger_entry.previous_hash == runs["clean"].ledger_entry.entry_hash
    assert runs["forgery"].ledger_entry.previous_hash == runs["injection"].ledger_entry.entry_hash


def test_summarize_orchestrated_run_returns_ui_ready_summary() -> None:
    summary = summarize_orchestrated_run(run_scenario("clean"))

    assert set(summary) == {
        "scenario",
        "run_id",
        "final_decision",
        "allow_execution",
        "token_issued",
        "mock_bank_status",
        "proof_hash",
        "ledger_entry_hash",
        "timeline_events_count",
    }


def test_orchestrator_does_not_decide_from_scenario_name() -> None:
    workflow = load_workflow()
    seed = load_scenario_seed("clean")
    modified_seed = seed.model_copy(update={"expected_tosco_decision": Decision.BLOCK})

    original_outcome = run_clearance(seed_to_run_context(seed), workflow)
    modified_outcome = run_clearance(seed_to_run_context(modified_seed), workflow)

    assert original_outcome.final_decision is Decision.ALLOW
    assert modified_outcome.final_decision is Decision.ALLOW


def test_orchestrator_is_deterministic() -> None:
    config = OrchestratorConfig()
    first = run_scenario("clean", config=config)
    second = run_scenario("clean", config=config)

    assert summarize_orchestrated_run(first) == summarize_orchestrated_run(second)
    assert first.timeline.event_types == second.timeline.event_types
    assert first.proof_packet.proof_hash() == second.proof_packet.proof_hash()
    assert first.execution_result.execution_reference == second.execution_result.execution_reference
