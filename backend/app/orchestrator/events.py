"""Deterministic event timeline models for orchestrated demo runs."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError, ValidationInfo, field_validator, model_validator


class EventType(StrEnum):
    """Enumerate every event the orchestrator can emit for a demo run."""

    AGENT_PROPOSED = "AGENT_PROPOSED"
    PLAN_STARTED = "PLAN_STARTED"
    EVIDENCE_RETRIEVED = "EVIDENCE_RETRIEVED"
    EXTRACTION_STARTED = "EXTRACTION_STARTED"
    EXTRACTION_SEALED = "EXTRACTION_SEALED"
    VULTR_EXTRACTION_STARTED = "VULTR_EXTRACTION_STARTED"
    VULTR_EXTRACTION_SUCCEEDED = "VULTR_EXTRACTION_SUCCEEDED"
    VULTR_EXTRACTION_FALLBACK = "VULTR_EXTRACTION_FALLBACK"
    TOOL_CALLED = "TOOL_CALLED"
    GATE_STARTED = "GATE_STARTED"
    GATE_COMPLETED = "GATE_COMPLETED"
    DECISION_MADE = "DECISION_MADE"
    PROOF_SEALED = "PROOF_SEALED"
    LEDGER_APPENDED = "LEDGER_APPENDED"
    CLEARANCE_TOKEN_ISSUED = "CLEARANCE_TOKEN_ISSUED"
    CLEARANCE_TOKEN_SKIPPED = "CLEARANCE_TOKEN_SKIPPED"
    EXECUTION_ATTEMPTED = "EXECUTION_ATTEMPTED"
    EXECUTION_ACCEPTED = "EXECUTION_ACCEPTED"
    EXECUTION_REJECTED = "EXECUTION_REJECTED"


def _require_non_empty(value: str, field_name: str) -> str:
    """Reject blank event fields that would weaken timeline readability."""

    trimmed = value.strip()
    if not trimmed:
        raise ValueError(f"{field_name} cannot be empty")
    return trimmed


class EventTimelineError(RuntimeError):
    """Signal invalid event timeline state or sequencing."""


class OrchestratorEvent(BaseModel):
    """Represent one deterministic event emitted during orchestration."""

    model_config = ConfigDict(extra="forbid")

    index: int
    event_type: str
    run_id: str
    title: str
    detail: str
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("index")
    @classmethod
    def validate_index(cls, value: int) -> int:
        """Reject negative event indices."""

        if value < 0:
            raise ValueError("index must be >= 0")
        return value

    @field_validator("event_type", "run_id", "title", "detail")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank core event fields."""

        return _require_non_empty(value, info.field_name)


class EventTimeline(BaseModel):
    """Hold the ordered event sequence for one orchestrated run."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    run_id: str
    events: list[OrchestratorEvent]

    @field_validator("run_id")
    @classmethod
    def validate_run_id(cls, value: str) -> str:
        """Reject blank run identifiers."""

        return _require_non_empty(value, "run_id")

    @field_validator("events")
    @classmethod
    def validate_non_empty_events(cls, value: list[OrchestratorEvent]) -> list[OrchestratorEvent]:
        """Reject empty timelines."""

        if not value:
            raise ValueError("events must not be empty")
        return value

    @model_validator(mode="after")
    def validate_sequence(self) -> "EventTimeline":
        """Ensure event indices are sequential and all events belong to the same run."""

        for expected_index, event in enumerate(self.events):
            if event.index != expected_index:
                raise ValueError("event indices must be exactly 0..n-1")
            if event.run_id != self.run_id:
                raise ValueError("all events must have the same run_id as the timeline")
        return self

    @property
    def event_types(self) -> list[str]:
        """Expose event type order for UI and tests."""

        return [event.event_type for event in self.events]

    @property
    def length(self) -> int:
        """Expose timeline length without recalculating in callers."""

        return len(self.events)


class TimelineBuilder:
    """Build one deterministic event timeline for a single run."""

    def __init__(self, run_id: str) -> None:
        self.run_id = _require_non_empty(run_id, "run_id")
        self._events: list[OrchestratorEvent] = []

    def add(
        self,
        event_type: str,
        title: str,
        detail: str,
        payload: dict[str, Any] | None = None,
    ) -> OrchestratorEvent:
        """Append one event in deterministic order with an auto-assigned index."""

        event = OrchestratorEvent(
            index=len(self._events),
            event_type=event_type,
            run_id=self.run_id,
            title=title,
            detail=detail,
            payload={} if payload is None else payload,
        )
        self._events.append(event)
        return event

    def build(self) -> EventTimeline:
        """Finalize the current event list into an immutable timeline model."""

        try:
            return EventTimeline(run_id=self.run_id, events=list(self._events))
        except ValidationError as exc:
            raise EventTimelineError(f"Invalid event timeline: {exc}") from exc
