"""Execution-scoped store for redacted answer fragments.

Mirrors `execution_events.ExecutionEventStore`: the synthesizer writes, the SSE
endpoint reads, and the two can only meet on a process-wide instance because the
RAG pipeline has no access to `app.state`.

Everything written here has already been through `StreamingRedactor`, which
emits only text whose redaction cannot still change. Nothing else may write to
this store -- an unredacted fragment reaching it is the same disclosure that
`output_filter` exists to prevent, just earlier.

The fragments are a *draft*. They carry no citation numbering and no reference
list: those are decided in `output_filter`, after the whole answer exists and
after DLP has settled which citations survive. The client shows the draft while
it is being written and replaces it with the final answer from the query
response.
"""

from __future__ import annotations

from collections import OrderedDict
from contextvars import ContextVar
from threading import RLock

# The execution whose answer fragments the current async task is producing.
# A ContextVar for the same reason execution_events uses one: the engine is
# cached and shared, so instance state would let one request's fragments land
# under another request's id.
current_answer_stream_id: ContextVar[str | None] = ContextVar("orchestration_current_answer_stream", default=None)

_MAX_EXECUTIONS = 512
_MAX_FRAGMENTS_PER_EXECUTION = 4_000
"""A runaway guard, not a budget: a long answer is a few hundred fragments."""


class AnswerStreamStore:
    """Retain redacted answer fragments long enough for one execution stream."""

    def __init__(
        self,
        *,
        max_executions: int = _MAX_EXECUTIONS,
        max_fragments_per_execution: int = _MAX_FRAGMENTS_PER_EXECUTION,
    ) -> None:
        self._fragments: OrderedDict[str, list[str]] = OrderedDict()
        self._complete: set[str] = set()
        self._max_executions = max_executions
        self._max_fragments = max_fragments_per_execution
        self._lock = RLock()

    def publish(self, execution_id: str, fragment: str) -> None:
        """Append one already-redacted fragment.

        Overflow drops the newest rather than the oldest, because `since`
        addresses fragments by offset and dropping from the front would shift
        every offset a live subscriber holds.
        """
        if not fragment:
            return
        with self._lock:
            fragments = self._fragments.get(execution_id)
            if fragments is None:
                fragments = []
                self._fragments[execution_id] = fragments
                while len(self._fragments) > self._max_executions:
                    evicted, _ = self._fragments.popitem(last=False)
                    self._complete.discard(evicted)
            else:
                self._fragments.move_to_end(execution_id)
            if len(fragments) < self._max_fragments:
                fragments.append(fragment)

    def complete(self, execution_id: str) -> None:
        """Mark that no further fragments are coming, so a reader can stop."""
        with self._lock:
            self._complete.add(execution_id)

    def since(self, execution_id: str, offset: int) -> tuple[str, ...]:
        with self._lock:
            return tuple(self._fragments.get(execution_id, ())[offset:])

    def is_complete(self, execution_id: str) -> bool:
        with self._lock:
            return execution_id in self._complete


_default_store = AnswerStreamStore()


def get_default_answer_stream_store() -> AnswerStreamStore:
    """Return the process-wide store shared by the synthesizer and the SSE route."""
    return _default_store


__all__ = [
    "AnswerStreamStore",
    "current_answer_stream_id",
    "get_default_answer_stream_store",
]
