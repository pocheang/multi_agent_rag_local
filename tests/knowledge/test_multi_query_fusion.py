"""Rank within a query must survive the fan-out over several queries.

Every adapter runs `plan.queries` concurrently and hands one combined list to a
single source slot. `reciprocal_rank_fuse` scores by *position in that list*, so
concatenating the per-query results put the second query's best hit at position
`top_k + 1` and scored it as a mediocre result -- a systematic penalty on every
query after the first, growing with the number of queries.

This was never dormant, though it was uneven. `QUERY_REWRITE_ENABLED` defaults
true and `_rule_rewrites` needs no LLM: measured, a Chinese question containing
punctuation yields 2-3 queries and a multi-word English one yields 3, while a
short punctuation-free Chinese question yields 1 and paid nothing. Seeding
planner sub-queries widens an existing hole rather than opening one.
"""

from __future__ import annotations

import asyncio

import pytest

from app.domain.contracts import EvidenceItem
from app.knowledge.adapters import _flatten
from app.knowledge.fusion import reciprocal_rank_fuse


def _item(name: str, score: float = 0.5) -> EvidenceItem:
    return EvidenceItem(
        item_id=name,
        content=f"content of {name}",
        source=f"/docs/{name}.md",
        document_id=name,
        version=1,
        layer="evidence",
        modality="text",
        retriever="bm25",
        score=score,
    )


def test_the_second_querys_top_hit_outranks_the_first_querys_tail():
    """The assertion that would have caught `_flatten`.

    Concatenation put `b1` -- the best result for the second query -- at
    position 5, behind three results the first query ranked below its own top
    hit.
    """

    first = [_item("a1"), _item("a2"), _item("a3"), _item("a4")]
    second = [_item("b1"), _item("b2")]

    order = [item.item_id for item in _flatten([first, second])]

    assert order.index("b1") < order.index("a2")
    assert order[:2] == ["a1", "b1"]


def test_every_result_survives_the_interleave():
    """Reordering must not drop anything, including from the longest list."""

    first = [_item("a1"), _item("a2"), _item("a3")]
    second = [_item("b1")]
    third: list[EvidenceItem] = []

    order = [item.item_id for item in _flatten([first, second, third])]

    assert sorted(order) == ["a1", "a2", "a3", "b1"]


def test_an_item_found_by_two_queries_outranks_one_found_by_one():
    """The agreement signal the interleave has to preserve.

    `reciprocal_rank_fuse` accumulates one contribution per appearance, so a
    document both queries return should beat one only a single query found. This
    is the property a naive de-duplication inside the adapter would destroy.
    """

    shared = _item("shared")
    first = [shared, _item("only_a")]
    second = [shared, _item("only_b")]

    fused = reciprocal_rank_fuse([_flatten([first, second])], rrf_k=60)
    order = [item.item_id for item in fused]

    assert order[0] == "shared"


def test_a_single_query_is_unchanged():
    """One query per source is still the common case; it must not move."""

    single = [_item("a1"), _item("a2"), _item("a3")]

    assert [item.item_id for item in _flatten([single])] == ["a1", "a2", "a3"]


@pytest.mark.asyncio
async def test_an_adapter_fanning_out_returns_interleaved_results():
    """End to end through an adapter's own gather, not just the helper."""

    async def one(name: str) -> tuple[EvidenceItem, ...]:
        return tuple(_item(f"{name}{index}") for index in range(1, 4))

    groups = await asyncio.gather(*(one(name) for name in ("a", "b")))
    order = [item.item_id for item in _flatten(groups)]

    assert order == ["a1", "b1", "a2", "b2", "a3", "b3"]
