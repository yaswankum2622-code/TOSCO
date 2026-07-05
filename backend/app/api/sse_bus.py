"""Per-run Server-Sent Events bus for the public TOSCO contract."""

from __future__ import annotations

import asyncio
import json
import threading
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationInfo, field_validator


def _require_non_empty(value: str, field_name: str) -> str:
    """Reject blank event-bus identifiers."""

    trimmed = value.strip()
    if not trimmed:
        raise ValueError(f"{field_name} cannot be empty")
    return trimmed


class ContractEventMessage(BaseModel):
    """One public-contract event payload emitted over SSE."""

    model_config = ConfigDict(extra="forbid")

    event: str
    run_id: str
    ts: str
    data: dict[str, Any]

    @field_validator("event", "run_id", "ts")
    @classmethod
    def validate_non_empty_strings(cls, value: str, info: ValidationInfo) -> str:
        """Reject blank event message fields."""

        return _require_non_empty(value, info.field_name)

    def to_sse_bytes(self) -> bytes:
        """Encode this event as one SSE message frame."""

        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True)
        return f"data: {payload}\n\n".encode("utf-8")


class RunSseBus:
    """Broadcast one run's public event history to any number of subscribers."""

    def __init__(self, run_id: str, loop: asyncio.AbstractEventLoop) -> None:
        self.run_id = _require_non_empty(run_id, "run_id")
        self._loop = loop
        self._history: list[ContractEventMessage] = []
        self._subscribers: set[asyncio.Queue[ContractEventMessage | None]] = set()
        self._complete = False
        self._lock = threading.Lock()

    def publish(self, event: str, data: dict[str, Any] | None = None) -> ContractEventMessage:
        """Append one event to history and fan it out to active subscribers."""

        message = ContractEventMessage(
            event=event,
            run_id=self.run_id,
            ts=datetime.now(timezone.utc).isoformat(),
            data={} if data is None else data,
        )

        with self._lock:
            self._history.append(message)
            subscribers = tuple(self._subscribers)

        for subscriber in subscribers:
            asyncio.run_coroutine_threadsafe(subscriber.put(message), self._loop)

        return message

    def complete(self) -> None:
        """Close the run stream so current subscribers can finish cleanly."""

        with self._lock:
            if self._complete:
                return
            self._complete = True
            subscribers = tuple(self._subscribers)

        for subscriber in subscribers:
            asyncio.run_coroutine_threadsafe(subscriber.put(None), self._loop)

    @property
    def history(self) -> list[ContractEventMessage]:
        """Return a stable copy of the emitted event history."""

        with self._lock:
            return list(self._history)

    @property
    def complete_state(self) -> bool:
        """Expose whether this run has finished emitting events."""

        with self._lock:
            return self._complete

    async def subscribe(self) -> AsyncIterator[ContractEventMessage]:
        """Yield backlog first, then any future events, until the run completes."""

        queue: asyncio.Queue[ContractEventMessage | None] = asyncio.Queue()
        with self._lock:
            backlog = list(self._history)
            is_complete = self._complete
            if not is_complete:
                self._subscribers.add(queue)

        try:
            for item in backlog:
                yield item

            if is_complete:
                return

            while True:
                next_item = await queue.get()
                if next_item is None:
                    break
                yield next_item
        finally:
            with self._lock:
                self._subscribers.discard(queue)
