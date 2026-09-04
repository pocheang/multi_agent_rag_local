"""Every query's rank-1 hit must be scored as a rank-1 hit.

A source runs each of `plan.queries` and used to hand one combined list to
`reciprocal_rank_fuse`, which scores by *position in the list*. Concatenating put
the second query's best hit at position `top_k + 1` and charged it a rank it had
not earned. Interleaving (the first fix) softened that -- rank 1 of query 2
landed at position 2 -- but did not remove it: the penalty just got smaller, and
it still grew with the number of queries.

Keeping the lists apart removes it. Each (source, query) pair is now its own
ranked list, so every query's rank-1 gets the same `1/(k+1)`, and a document that
two queries both rank first accumulates two full contributions instead of one
full and one discounted.

`flatten_ranked_groups` survives, but only as the flat *view* -- what counts,
diagnostics and the graph adapter's prior evidence read. Nothing about ranking
depends on it any more.
"""

from __future__ import annotations

import asyncio

import pytest

from app.domain.contracts import EvidenceItem
from app.knowledge.adapters import flatten_ranked_groups
from app.knowledge.fusion import reciprocal_rank_fuse

RRF_K = 60


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


# --- the property the split exists for --------------------------------------


def test_each_querys_top_hit_is_scored_as_a_top_hit():
    """The assertion that would have caught it.

    Concatenated, `b1` was scored at rank 5. Interleaved, at rank 2. Only as its
    own list does it score what it earned.
    """

    first = (_item("a1"), _item("a2"), _item("a3"), _item("a4"))
    second = (_item("b1"), _item("b2"))

    fused = reciprocal_rank_fuse((first, second), rrf_k=RRF_K)
    by_id = {item.item_id: item.score for item in fused}

    assert by_id["a1"] == pytest.approx(by_id["b1"])


def test_agreement_between_queries_outranks_a_single_first_place():
    """A document both queries rank first should beat one only a single query
    found. This is the signal a source-level fold blurs."""

    shared = _item("shared")
    fused = reciprocal_rank_fuse(
        ((shared, _item("only_a")), (shared, _item("only_b"))),
        rrf_k=RRF_K,
    )

    assert [item.item_id for item in fused][0] == "shared"


def test_a_second_querys_tail_does_not_outrank_a_first_querys_head():
    """The split must not overcorrect: rank 3 of one query is still worse than
    rank 1 of another."""

    fused = reciprocal_rank_fuse(
        ((_item("a1"), _item("a2"), _item("a3")), (_item("b1"), _item("b2"), _item("b3"))),
        rrf_k=RRF_K,
    )
    order = [item.item_id for item in fused]

    assert order.index("a1") < order.index("b3")
    assert order.index("b1") < order.index("a3")


# --- the flat view -----------------------------------------------------------


def test_the_flat_view_interleaves_and_keeps_everything():
    """`items` feeds counts, diagnostics and the graph adapter's prior evidence.
    Interleaved because a flat list still reads better that way; nothing about
    ranking depends on it."""

    first = (_item("a1"), _item("a2"), _item("a3"))
    second = (_item("b1"),)

    order = [item.item_id for item in flatten_ranked_groups((first, second, ()))]

    assert order == ["a1", "b1", "a2", "a3"]


def test_a_single_query_is_unchanged():
    single = (_item("a1"), _item("a2"), _item("a3"))

    assert [item.item_id for item in flatten_ranked_groups((single,))] == ["a1", "a2", "a3"]


@pytest.mark.asyncio
async def test_an_adapter_returns_one_list_per_query():
    """The shape the orchestrator validates: a tuple of ranked tuples, in the
    order of `plan.queries`."""

    async def one(name: str) -> tuple[EvidenceItem, ...]:
        return tuple(_item(f"{name}{index}") for index in range(1, 3))

    groups = tuple(await asyncio.gather(*(one(name) for name in ("a", "b"))))

    assert [[item.item_id for item in group] for group in groups] == [["a1", "a2"], ["b1", "b2"]]
