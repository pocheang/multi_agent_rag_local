"""Execution-event publisher abstractions with a deterministic test implementation."""

from __future__ import annotations

from typing import Protocol

from app.domain.events import ExecutionEvent


class EventPublisher(Protocol):
    """Publish a safe execution event without coupling the engine to SSE."""

    async def publish(self, event: ExecutionEvent) -> None:
        """Deliver one event to the configured trace sink."""


class NullEventPublisher:
    """Default publisher used before API/SSE delivery is introduced."""

    async def publish(self, event: ExecutionEvent) -> None:
        """Intentionally drop the event while retaining the same async boundary."""
        del event


class InMemoryEventPublisher:
    """Append events in order for unit tests and in-process callers."""

    def __init__(self) -> None:
        self.events: list[ExecutionEvent] = []

    async def publish(self, event: ExecutionEvent) -> None:
        self.events.append(event)
