"""The router cache must not need an event loop.

`decide_route` is synchronous and runs inside `asyncio.to_thread`, where there is
no running loop. The cache behind it was async, driven with
`loop.run_until_complete`, so every worker thread reached
`asyncio.new_event_loop()` and left one open for the life of the process. A route
decision is a dictionary lookup; it never needed a loop at all.
"""

from __future__ import annotations

import asyncio
import pathlib
import threading
import time

from app.agents.shared import cache as router_cache
from app.agents.shared.cache import _TTLCache, cached_router_decision, clear_router_decision_cache


def test_a_cached_lookup_opens_no_event_loop():
    """The property the old implementation could not hold."""
    clear_router_decision_cache()
    calls: list[str] = []

    @cached_router_decision
    def decide(question: str, **_kwargs) -> str:
        calls.append(question)
        return f"route:{question}"

    loops: list[object] = []

    def worker() -> None:
        decide("what is rag")
        decide("what is rag")
        try:
            loops.append(asyncio.get_event_loop_policy().get_event_loop())
        except RuntimeError:
            loops.append(None)

    thread = threading.Thread(target=worker)
    thread.start()
    thread.join()

    assert calls == ["what is rag"], "second call should have been served from cache"
    assert loops == [None], "a worker thread must not be left holding an event loop"


def test_the_cache_still_serves_repeat_questions():
    clear_router_decision_cache()
    calls: list[str] = []

    @cached_router_decision
    def decide(question: str, **_kwargs) -> str:
        calls.append(question)
        return question.upper()

    assert decide("a") == "A"
    assert decide("a") == "A"
    assert decide("b") == "B"
    assert calls == ["a", "b"]


def test_the_key_separates_different_routing_configurations():
    clear_router_decision_cache()
    calls: list[tuple] = []

    @cached_router_decision
    def decide(question: str, **kwargs) -> str:
        calls.append((question, kwargs.get("use_reasoning")))
        return "route"

    decide("a", use_reasoning=False)
    decide("a", use_reasoning=True)

    assert len(calls) == 2


def test_it_works_inside_a_running_loop_too():
    """Both call shapes exist: `asyncio.to_thread` (no loop) and a direct call
    from async code (loop running). `run_until_complete` raised in the second."""
    clear_router_decision_cache()

    @cached_router_decision
    def decide(question: str, **_kwargs) -> str:
        return "route"

    async def main() -> str:
        return decide("inside a loop")

    assert asyncio.run(main()) == "route"


# --- the store itself --------------------------------------------------------


def test_entries_expire():
    store = _TTLCache(max_size=8, ttl_seconds=0.05)
    store.set("k", "v")

    assert store.get("k") == "v"
    time.sleep(0.06)
    assert store.get("k") is None


def test_the_least_recently_used_entry_is_evicted_first():
    store = _TTLCache(max_size=2, ttl_seconds=60)
    store.set("a", 1)
    store.set("b", 2)
    store.get("a")  # a is now the most recently used
    store.set("c", 3)

    assert store.get("a") == 1
    assert store.get("b") is None
    assert store.get("c") == 3


def test_concurrent_writers_do_not_corrupt_the_store():
    store = _TTLCache(max_size=64, ttl_seconds=60)

    def worker(offset: int) -> None:
        for index in range(200):
            store.set(f"k{(offset + index) % 64}", index)
            store.get(f"k{index % 64}")

    threads = [threading.Thread(target=worker, args=(offset,)) for offset in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert len(store._entries) <= 64


def test_the_module_no_longer_reaches_for_a_loop():
    """A structural check: the fix is that this code is synchronous.

    Parsed rather than grepped -- the docstring explains the old behaviour and
    names both calls, and a text search cannot tell an explanation from a call.
    """
    import ast

    tree = ast.parse(pathlib.Path(router_cache.__file__).read_text(encoding="utf-8"))
    called = {
        node.func.attr for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
    }

    assert "run_until_complete" not in called
    assert "new_event_loop" not in called
