"""Two claims that were false in the same way: reporting an outcome you did not have.

**A cancelled task must end cancelled.** `_cleanup_loop` caught
`asyncio.CancelledError` and `break`, so the coroutine finished *normally*.
`await task` after `task.cancel()` then returned without raising, and nothing
downstream could distinguish "stopped when asked" from "finished on its own".
The absorbing belongs in `stop_periodic_cleanup`, which is the caller that asked
for the cancellation -- and that one keeps its `except: pass` deliberately.

**A store must not report a write it did not make.** `_save_file_sessions`
logged the failure and returned nothing; `set()` returned a hardcoded `True`
either way. A caller was told the session was stored when the file write had
failed, which for a session store means a login that will not survive.

Neither was reachable through the test suite, which is why both survived: one
needs a cancellation, the other needs the disk to refuse.
"""

from __future__ import annotations

import asyncio
import json
import shutil
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def session_dir():
    """Deliberately not pytest's `tmp_path`: its basetemp root needs directory
    permissions that are not available on every Windows checkout, the same reason
    `tests/agents/test_closed_loops.py` builds its own."""

    root = Path(tempfile.mkdtemp(prefix="querymind-sessions-"))
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


class TestCancellationPropagates:
    @pytest.mark.asyncio
    async def test_the_cleanup_loop_ends_cancelled_not_merely_finished(self) -> None:
        from app.services.observability.agent_execution_tracker import AgentExecutionTracker

        tracker = AgentExecutionTracker()
        task = asyncio.create_task(tracker._cleanup_loop(3600))
        await asyncio.sleep(0)  # let it reach the first await
        task.cancel()

        with pytest.raises(asyncio.CancelledError):
            await task

        assert task.cancelled(), "the task finished normally, so its canceller cannot tell it was cancelled"

    @pytest.mark.asyncio
    async def test_stopping_absorbs_the_cancellation_it_asked_for(self) -> None:
        """The other half: the caller that cancels does not re-raise at its own callers."""

        from app.services.observability.agent_execution_tracker import AgentExecutionTracker

        tracker = AgentExecutionTracker()
        await tracker.start_periodic_cleanup(3600)

        await tracker.stop_periodic_cleanup()  # must not raise

        assert tracker._cleanup_task is None


class TestTheSessionStoreTellsTheTruth:
    def _store(self, session_dir):
        from app.services.auth.enhanced_session import SessionStore

        store = SessionStore.__new__(SessionStore)
        store.use_redis = False
        store.redis_client = None
        store.fallback_path = session_dir / "sessions.json"
        store.fallback_path.parent.mkdir(parents=True, exist_ok=True)
        return store

    def test_a_stored_session_reports_success(self, session_dir) -> None:
        store = self._store(session_dir)

        assert store.set("abc", {"user": "alice"}) is True
        assert json.loads(store.fallback_path.read_text(encoding="utf-8"))["abc"]["data"] == {"user": "alice"}

    def test_a_failed_write_is_not_reported_as_success(self, session_dir, monkeypatch) -> None:
        """The defect: the caller was told the login had been stored."""

        store = self._store(session_dir)

        def refuse(*args, **kwargs):
            raise OSError("disk is full")

        monkeypatch.setattr("builtins.open", refuse)

        assert store.set("abc", {"user": "alice"}) is False
