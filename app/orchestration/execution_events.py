"""Thread-safe, execution-scoped store for browser-safe execution events."""

from __future__ import annotations

from collections import defaultdict
from threading import RLock

from app.domain.events import ExecutionEvent


class ExecutionEventStore:
    """Retain only typed UI-safe events long enough for one execution stream."""

    def __init__(self) -> None:
        self._events: dict[str, list[ExecutionEvent]] = defaultdict(list)
        self._lock = RLock()

    def publish(self, execution_id: str, event: ExecutionEvent) -> None:
        """Append one immutable event under the execution that produced it."""
        with self._lock:
            self._events[execution_id].append(event)

    def events_since(self, execution_id: str, offset: int) -> tuple[ExecutionEvent, ...]:
        """Return an immutable ordered slice without leaking storage internals."""
        with self._lock:
            return tuple(self._events.get(execution_id, ())[offset:])
