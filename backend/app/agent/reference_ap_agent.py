"""Minimal reference AP agent for proposing seeded vendor payments."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator

from app.models import ActionIntent, RunContext, SealedExtraction
from app.scenarios.loader import ScenarioSeed


def _require_non_empty(value: str, field_name: str) -> str:
    """Reject blank agent proposal strings."""

    trimmed = value.strip()
    if not trimmed:
        raise ValueError(f"{field_name} cannot be empty")
    return trimmed


class ReferenceAgentError(RuntimeError):
    """Signal invalid reference-agent inputs or proposal construction errors."""


class AgentProposal(BaseModel):
    """Represent the naive AP agent's proposal before TOSCO clearance."""

    model_config = ConfigDict(extra="forbid")

    scenario: str
    intent: ActionIntent
    naive_action: str
    proposed_reason: str

    @field_validator("scenario", "naive_action", "proposed_reason")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank proposal strings."""

        return _require_non_empty(value, info.field_name)


def _build_intent_from_seed(seed: ScenarioSeed) -> ActionIntent:
    """Build the ActionIntent the reference AP agent would emit from a seed."""

    evidence_refs: list[str] = []
    for evidence_type in sorted(seed.evidence):
        value = seed.evidence[evidence_type]
        if isinstance(value, dict):
            doc_id = value.get("doc_id")
            if isinstance(doc_id, str) and doc_id.strip():
                evidence_refs.append(doc_id.strip())
                continue
        evidence_refs.append(evidence_type)

    return ActionIntent(
        intent_id=seed.intent_id,
        agent_id=seed.agent_id,
        workflow=seed.workflow_id,
        action=seed.proposed_action,
        evidence_refs=evidence_refs,
        declared_confidence=0.94,
        requested_mode="assisted",
    )


class ReferenceAPAgent:
    """Simulate a naive AP agent that proposes payments from seeded documents."""

    _REASONS = {
        "clean": "Invoice, PO, and GRN appear matched, so the AP agent proposes payment.",
        "injection": "The AP agent follows invoice instructions and proposes the attacker-routed payment.",
        "forgery": "The AP agent sees internally consistent documents and proposes payment to the updated bank account.",
    }

    def propose_from_seed(self, seed: ScenarioSeed) -> AgentProposal:
        """Build the naive AP payment proposal from scenario seed data only."""

        try:
            proposed_reason = self._REASONS[seed.scenario]
        except KeyError as exc:
            raise ReferenceAgentError(
                f"Unsupported scenario '{seed.scenario}' for ReferenceAPAgent"
            ) from exc

        return AgentProposal(
            scenario=seed.scenario,
            intent=_build_intent_from_seed(seed),
            naive_action=seed.expected_naive_agent_action,
            proposed_reason=proposed_reason,
        )


def build_run_context_from_agent_proposal(
    seed: ScenarioSeed,
    proposal: AgentProposal,
    *,
    extraction_fields: dict[str, Any] | None = None,
    source_spans: dict[str, list[int]] | None = None,
    extractor: str = "sandbox-fallback",
    fallback_mode: bool = True,
) -> RunContext:
    """Convert an agent proposal plus seed data into a deterministic RunContext."""

    if proposal.scenario != seed.scenario:
        raise ReferenceAgentError(
            f"Proposal scenario '{proposal.scenario}' does not match seed scenario '{seed.scenario}'"
        )

    extraction = SealedExtraction(
        doc_id=seed.evidence.get("invoice", {}).get("doc_id", f"{seed.scenario}-invoice"),
        fields=seed.extraction_fields if extraction_fields is None else extraction_fields,
        source_spans=seed.source_spans if source_spans is None else source_spans,
        extractor=extractor,
    )
    return RunContext(
        run_id=seed.run_id,
        intent=proposal.intent,
        workflow_id=seed.workflow_id,
        extraction=extraction,
        evidence=seed.evidence,
        signals=seed.signals,
        fallback_mode=fallback_mode,
    )
