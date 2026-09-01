"""The graph route's memo caches run inside `asyncio.to_thread`, not on the loop.

`app/agents/rag/cache.py` wrapped an async cache by calling
`asyncio.get_event_loop()` and `run_until_complete`. `run_graph_rag` reaches it
from a worker thread, where `get_event_loop()` raises and the fallback installed
a private, never-closed loop per worker -- and an `asyncio.Lock` driven from
several loops serializes nothing. Nothing reached the code, so nothing failed.

These pin the two shapes that broke: a call from a pool worker, and a call from
the main thread while a loop is running.
"""

from __future__ import annotations

import asyncio
from concurrent.futures import ThreadPoolExecutor

from app.agents.rag.cache import cached_pdf_quality, clear_all_caches, get_cache_stats

_METADATA = {"page": 1, "total_pages": 40, "format": "markdown"}


@cached_pdf_quality
def _score(text: str, metadata: dict) -> float:
    return float(len(text) % 10) / 10


def test_scoring_works_from_a_pool_worker() -> None:
    clear_all_caches()

    async def run() -> list[float]:
        return list(await asyncio.gather(*(asyncio.to_thread(_score, f"doc {i}", _METADATA) for i in range(8))))

    assert len(asyncio.run(run())) == 8


def test_scoring_works_while_a_loop_is_running() -> None:
    """The opposite failure: `run_until_complete` on a running loop raises, so a
    synchronous caller inside a request would have taken down the graph route."""
    clear_all_caches()

    async def run() -> float:
        return _score("inline call", _METADATA)

    assert isinstance(asyncio.run(run()), float)


def test_the_cache_actually_caches_across_threads() -> None:
    """One shared memo, not one per worker: per-thread state would make the hit
    rate depend on which worker the pool happened to pick."""
    clear_all_caches()

    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: _score("same document", _METADATA), range(12)))

    stats = get_cache_stats()["pdf_quality"]
    assert stats["hits"] >= 8
    assert stats["size"] == 1
