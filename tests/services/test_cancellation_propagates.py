"""A cancelled task must end cancelled.

`_cleanup_loop` caught `asyncio.CancelledError` and `break`, so the coroutine
finished *normally*. `await task` after `task.cancel()` then returned without
raising, and nothing downstream could distinguish "stopped when asked" from
"finished on its own". The absorbing belongs in `stop_periodic_cleanup`, which
is the caller that asked for the cancellation -- and that one keeps its
`except: pass` deliberately.

This file also held the SessionStore write-truth tests until 2026-09-02. They
went with `app/services/auth/enhanced_session.py`: its only production entry
point was the CSRF middleware, which required a cookie nothing set, so the
module they pinned had no reader on any request path.
"""

from __future__ import annotations

import asyncio

import pytest


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
