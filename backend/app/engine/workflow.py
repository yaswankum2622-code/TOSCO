"""Load and validate workflow configuration from YAML."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from app.models import WorkflowDefinition


class WorkflowLoadError(ValueError):
    """Signal that workflow configuration cannot be trusted or used."""


KNOWN_GATE_IDS = frozenset(
    {
        "G1_EVIDENCE",
        "G2_GROUNDEDNESS",
        "G3_POLICY",
        "G4_RISK",
        "G5_REALITY",
        "G6_DECISION_SEAL",
    }
)


def _as_path(path: str | Path) -> Path:
    """Normalize workflow loader inputs to a pathlib Path."""

    return Path(path).expanduser()


def _read_yaml_mapping(path: Path) -> dict[str, Any]:
    """Read YAML as a mapping because workflows are declarative objects."""

    if not path.exists() or not path.is_file():
        raise WorkflowLoadError(f"Workflow file not found: {path}")

    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as exc:
        raise WorkflowLoadError(f"Unable to read workflow file {path}: {exc}") from exc

    try:
        payload = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise WorkflowLoadError(f"Invalid YAML in workflow file {path}: {exc}") from exc

    if not isinstance(payload, dict):
        raise WorkflowLoadError(f"Workflow file {path} must contain a mapping at the root")

    return payload


def _duplicate_items(values: list[str]) -> list[str]:
    """Find duplicates while preserving first-seen order for clearer errors."""

    seen: set[str] = set()
    duplicates: list[str] = []
    for value in values:
        if value in seen and value not in duplicates:
            duplicates.append(value)
        seen.add(value)
    return duplicates


def _duplicate_registry_ids(
    registry_sources: dict[str, Path],
    workflow_id: str,
    new_source: Path,
) -> None:
    """Reject duplicate workflow IDs with both source files for debugging."""

    if workflow_id in registry_sources:
        original_source = registry_sources[workflow_id].name
        raise WorkflowLoadError(
            f"Duplicate workflow_id '{workflow_id}' found in {original_source} and {new_source.name}"
        )


def _require_non_empty_string_list(values: list[str], field_name: str, workflow_id: str) -> None:
    """Reject empty or blank string lists in workflow config."""

    if not values:
        raise WorkflowLoadError(
            f"Workflow '{workflow_id}' must define at least one {field_name}"
        )

    blanks = [value for value in values if not isinstance(value, str) or not value.strip()]
    if blanks:
        raise WorkflowLoadError(
            f"Workflow '{workflow_id}' has blank entries in {field_name}"
        )


def _validate_extraction_schema(extraction_schema: dict[str, Any], workflow_id: str) -> None:
    """Reject extraction schema shapes that later engine units cannot trust."""

    required_fields = extraction_schema.get("required_fields")
    if not isinstance(required_fields, list) or not required_fields:
        raise WorkflowLoadError(
            f"Workflow '{workflow_id}' must define a non-empty extraction_schema.required_fields list"
        )

    if any(not isinstance(field, str) or not field.strip() for field in required_fields):
        raise WorkflowLoadError(
            f"Workflow '{workflow_id}' has invalid extraction_schema.required_fields entries"
        )


def validate_workflow_definition(workflow: WorkflowDefinition) -> WorkflowDefinition:
    """Centralize workflow validation so every load path enforces the same rules."""

    workflow_id = workflow.workflow_id
    _require_non_empty_string_list(
        workflow.required_evidence_types,
        "required_evidence_types",
        workflow_id,
    )
    _require_non_empty_string_list(
        workflow.gates_to_run,
        "gates_to_run",
        workflow_id,
    )
    _require_non_empty_string_list(
        workflow.tools_to_call,
        "tools_to_call",
        workflow_id,
    )
    _validate_extraction_schema(workflow.extraction_schema, workflow_id)

    unknown_gate_ids = [gate_id for gate_id in workflow.gates_to_run if gate_id not in KNOWN_GATE_IDS]
    if unknown_gate_ids:
        unknown_text = ", ".join(unknown_gate_ids)
        raise WorkflowLoadError(
            f"Workflow '{workflow_id}' references unknown gate IDs: {unknown_text}"
        )

    duplicate_gate_ids = _duplicate_items(workflow.gates_to_run)
    if duplicate_gate_ids:
        duplicate_text = ", ".join(duplicate_gate_ids)
        raise WorkflowLoadError(
            f"Workflow '{workflow_id}' declares duplicate gate IDs: {duplicate_text}"
        )

    return workflow


def load_workflow_definition(path: str | Path) -> WorkflowDefinition:
    """Load one workflow definition from disk because config is the engine contract."""

    workflow_path = _as_path(path)
    payload = _read_yaml_mapping(workflow_path)

    try:
        workflow = WorkflowDefinition.model_validate(payload)
    except ValidationError as exc:
        raise WorkflowLoadError(
            f"Workflow file {workflow_path} failed WorkflowDefinition validation: {exc}"
        ) from exc

    return validate_workflow_definition(workflow)


def load_workflow_registry(workflows_dir: str | Path) -> dict[str, WorkflowDefinition]:
    """Load every workflow file from a directory into a deterministic registry."""

    directory = _as_path(workflows_dir)
    if not directory.exists() or not directory.is_dir():
        raise WorkflowLoadError(f"Workflows directory not found: {directory}")

    workflow_files = sorted(
        [*directory.glob("*.yaml"), *directory.glob("*.yml")],
        key=lambda path: path.name,
    )

    registry: dict[str, WorkflowDefinition] = {}
    registry_sources: dict[str, Path] = {}
    for workflow_file in workflow_files:
        workflow = load_workflow_definition(workflow_file)
        _duplicate_registry_ids(registry_sources, workflow.workflow_id, workflow_file)
        registry[workflow.workflow_id] = workflow
        registry_sources[workflow.workflow_id] = workflow_file

    return registry


def get_workflow(
    registry: dict[str, WorkflowDefinition],
    workflow_id: str,
) -> WorkflowDefinition:
    """Fetch a workflow by ID because later engine units should fail loudly on drift."""

    try:
        return registry[workflow_id]
    except KeyError as exc:
        available = ", ".join(sorted(registry)) or "<none>"
        raise WorkflowLoadError(
            f"Workflow '{workflow_id}' not found. Available workflows: {available}"
        ) from exc
