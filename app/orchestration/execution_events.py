"""Thread-safe, execution-scoped store for browser-safe execution events."""

from __future__ import annotations

from collections import OrderedDict
from contextvars import ContextVar
from threading import RLock

from app.domain.events import ExecutionEvent

# The execution whose events the current async task is producing.  A ContextVar
# rather than publisher state because OrchestrationEngine is cached and shared
# across concurrent requests (see _ENGINE_CACHE in app/pipeline/rag_pipeline.py);
# instance state would let request B's id capture request A's events.  The
# engine binds this in _execute, mirroring _current_event_reporter.
current_execution_id: ContextVar[str | None] = ContextVar("orchestration_current_execution_id", default=None)

# Ordinary runs emit ~13 events, so both caps are runaway guards, not budgets.
# Without them the store grows for the process lifetime: nothing ever deletes
# from it, and every query now writes to it.
_MAX_EXECUTIONS = 512
_MAX_EVENTS_PER_EXECUTION = 200


class ExecutionEventStore:
    """Retain only typed UI-safe events long enough for one execution stream."""

    def __init__(
        self,
        *,
        max_executions: int = _MAX_EXECUTIONS,
        max_events_per_execution: int = _MAX_EVENTS_PER_EXECUTION,
    ) -> None:
        self._events: OrderedDict[str, list[ExecutionEvent]] = OrderedDict()
        self._max_executions = max_executions
        self._max_events_per_execution = max_events_per_execution
        self._lock = RLock()

    def publish(self, execution_id: str, event: ExecutionEvent) -> None:
        """Append one immutable event under the execution that produced it.

        Evicts whole executions least-recently-written first.  Within one
        execution the overflow event is dropped rather than the oldest, because
        ``events_since`` addresses events by offset: dropping from the front
        would shift every offset a live SSE subscriber is holding.
        """
        with self._lock:
            events = self._events.get(execution_id)
            if events is None:
                events = []
                self._events[execution_id] = events
                while len(self._events) > self._max_executions:
                    self._events.popitem(last=False)
            else:
                self._events.move_to_end(execution_id)
            if len(events) < self._max_events_per_execution:
                events.append(event)

    def events_since(self, execution_id: str, offset: int) -> tuple[ExecutionEvent, ...]:
        """Return an immutable ordered slice without leaking storage internals."""
        with self._lock:
            return tuple(self._events.get(execution_id, ())[offset:])


_default_store = ExecutionEventStore()


def get_default_execution_event_store() -> ExecutionEventStore:
    """Return the process-wide store shared by the pipeline, tools, and SSE.

    The RAG pipeline has no access to ``app.state``, so the writer and the
    reader can only meet on a process-wide instance.  ``build_app_services``
    hands out this same object, which is what makes pipeline events visible to
    ``GET /api/v1/orchestration/executions/{execution_id}/events``.
    """
    return _default_store
