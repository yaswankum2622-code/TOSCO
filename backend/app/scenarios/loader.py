"""Load deterministic scenario seeds for the TOSCO demo."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, ValidationInfo, field_validator

from app.models import ActionIntent, Decision, ProposedAction, RunContext, SealedExtraction


SCENARIO_ORDER = ("clean", "injection", "forgery")
SCENARIOS = frozenset(SCENARIO_ORDER)


def _require_non_empty(value: str, field_name: str) -> str:
    """Reject blank seed fields that weaken deterministic setup."""

    trimmed = value.strip()
    if not trimmed:
        raise ValueError(f"{field_name} cannot be empty")
    return trimmed


class ScenarioLoadError(RuntimeError):
    """Signal invalid or missing scenario seed data."""


class ScenarioSeed(BaseModel):
    """Represent one deterministic vendor-payment demo scenario."""

    model_config = ConfigDict(extra="forbid")

    scenario: str
    title: str
    description: str
    agent_behavior: str
    run_id: str
    intent_id: str
    agent_id: str = "reference-ap-agent"
    workflow_id: str = "vendor_payment"
    proposed_action: ProposedAction
    evidence: dict[str, Any]
    extraction_fields: dict[str, Any]
    source_spans: dict[str, list[int]]
    signals: dict[str, Any]
    expected_naive_agent_action: str
    expected_tosco_decision: Decision

    @field_validator(
        "scenario",
        "title",
        "description",
        "agent_behavior",
        "run_id",
        "intent_id",
        "agent_id",
        "workflow_id",
        "expected_naive_agent_action",
    )
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank scenario metadata strings."""

        return _require_non_empty(value, info.field_name)

    @field_validator("evidence", "extraction_fields", "source_spans")
    @classmethod
    def validate_non_empty_mappings(
        cls,
        value: dict[str, Any],
        info: ValidationInfo,
    ) -> dict[str, Any]:
        """Reject seeds missing essential structured sections."""

        if not value:
            raise ValueError(f"{info.field_name} must not be empty")
        return value


def _default_seeds_dir() -> Path:
    """Resolve the default scenario seed directory relative to the app package."""

    return Path(__file__).resolve().parents[1] / "seeds"


def _resolve_seeds_dir(seeds_dir: str | Path | None) -> Path:
    """Normalize the seed directory input for deterministic file loading."""

    if seeds_dir is None:
        return _default_seeds_dir()
    return Path(seeds_dir)


def _read_seed_payload(path: Path) -> dict[str, Any]:
    """Read a scenario seed file as a JSON object."""

    if not path.exists() or not path.is_file():
        raise ScenarioLoadError(f"Scenario seed file not found: {path}")

    try:
        raw_payload = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ScenarioLoadError(f"Unable to read scenario seed file {path}: {exc}") from exc

    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise ScenarioLoadError(f"Invalid JSON in scenario seed file {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise ScenarioLoadError(f"Scenario seed file {path} must contain a JSON object")

    return payload


def _evidence_refs(evidence: dict[str, Any]) -> list[str]:
    """Build deterministic evidence references for ActionIntent payloads."""

    refs: list[str] = []
    for evidence_type in sorted(evidence):
        value = evidence[evidence_type]
        if isinstance(value, dict):
            doc_id = value.get("doc_id")
            if isinstance(doc_id, str) and doc_id.strip():
                refs.append(doc_id.strip())
                continue
        refs.append(evidence_type)
    return refs


def _intent_from_seed(seed: ScenarioSeed) -> ActionIntent:
    """Build the ActionIntent the reference AP agent would propose from a seed."""

    return ActionIntent(
        intent_id=seed.intent_id,
        agent_id=seed.agent_id,
        workflow=seed.workflow_id,
        action=seed.proposed_action,
        evidence_refs=_evidence_refs(seed.evidence),
        declared_confidence=0.94,
        requested_mode="assisted",
    )


def load_scenario_seed(name: str, seeds_dir: str | Path | None = None) -> ScenarioSeed:
    """Load one named scenario seed from disk for deterministic demo setup."""

    normalized_name = name.strip().lower()
    if normalized_name not in SCENARIOS:
        allowed = ", ".join(SCENARIO_ORDER)
        raise ScenarioLoadError(
            f"Invalid scenario name '{name}'. Allowed scenarios: {allowed}"
        )

    path = _resolve_seeds_dir(seeds_dir) / f"{normalized_name}.json"
    payload = _read_seed_payload(path)

    try:
        seed = ScenarioSeed.model_validate(payload)
    except ValidationError as exc:
        raise ScenarioLoadError(f"Scenario seed validation failed for {path}: {exc}") from exc

    return seed


def load_all_scenario_seeds(
    seeds_dir: str | Path | None = None,
) -> dict[str, ScenarioSeed]:
    """Load every supported scenario seed in deterministic demo order."""

    resolved_dir = _resolve_seeds_dir(seeds_dir)
    seeds: dict[str, ScenarioSeed] = {}
    for name in SCENARIO_ORDER:
        seed = load_scenario_seed(name, resolved_dir)
        seeds[name] = seed
    return seeds


def seed_to_run_context(seed: ScenarioSeed) -> RunContext:
    """Convert one scenario seed into the engine RunContext without leaking expectations."""

    intent = _intent_from_seed(seed)
    extraction = SealedExtraction(
        doc_id=seed.evidence.get("invoice", {}).get("doc_id", f"{seed.scenario}-invoice"),
        fields=seed.extraction_fields,
        source_spans=seed.source_spans,
    )
    return RunContext(
        run_id=seed.run_id,
        intent=intent,
        workflow_id=seed.workflow_id,
        extraction=extraction,
        evidence=seed.evidence,
        signals=seed.signals,
        fallback_mode=True,
    )
