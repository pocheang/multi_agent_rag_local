"""The async guard must not block the event loop while waiting for a slot.

QueryLoadGuard waits on a threading semaphore for up to acquire_timeout_ms.
Entering it inline from an async handler froze every other task on the loop
exactly when the server was saturated.
"""

from __future__ import annotations

import asyncio

import pytest

from app.services.query.guard import QueryLoadGuard, QueryOverloadedError


def _guard(**overrides) -> QueryLoadGuard:
    kwargs = dict(
        per_user_max_requests=1000,
        per_user_window_seconds=60,
        max_concurrent=1,
        max_waiting=4,
        acquire_timeout_ms=1000,
        backend="memory",
    )
    kwargs.update(overrides)
    return QueryLoadGuard(**kwargs)


@pytest.mark.asyncio
async def test_event_loop_stays_responsive_while_a_slot_is_held():
    guard = _guard()
    ticks = 0

    async def heartbeat():
        nonlocal ticks
        for _ in range(20):
            await asyncio.sleep(0.01)
            ticks += 1

    async def holder():
        async with guard.acquire_async("u1"):
            await asyncio.sleep(0.15)

    async def waiter():
        await asyncio.sleep(0.02)
        async with guard.acquire_async("u2"):
            pass

    beat = asyncio.create_task(heartbeat())
    await asyncio.gather(holder(), waiter())
    await beat

    # A blocking acquire would have frozen the heartbeat for the whole wait.
    assert ticks >= 10


@pytest.mark.asyncio
async def test_slot_is_released_after_the_block():
    guard = _guard()
    async with guard.acquire_async("u1"):
        pass
    async with guard.acquire_async("u1") as stats:
        assert int(stats["inflight"]) == 1


@pytest.mark.asyncio
async def test_slot_is_released_when_the_body_raises():
    guard = _guard()
    with pytest.raises(ValueError):
        async with guard.acquire_async("u1"):
            raise ValueError("boom")
    # If the exit had leaked the permit this would time out instead.
    async with guard.acquire_async("u1"):
        pass


@pytest.mark.asyncio
async def test_queue_full_still_raises():
    guard = _guard(max_waiting=0, acquire_timeout_ms=1000)

    async def holder():
        async with guard.acquire_async("u1"):
            await asyncio.sleep(0.2)

    task = asyncio.create_task(holder())
    await asyncio.sleep(0.05)
    with pytest.raises(QueryOverloadedError):
        async with guard.acquire_async("u2"):
            pass
    await task
