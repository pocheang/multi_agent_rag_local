"""What collect_candidates does, pinned before it was split up.

It was one 120-line function holding six jobs: choose the retrieval width, choose
the fusion weights, expand the query into variants, gather vector hits from one of
three possible places, gather BM25 hits, and fuse the two into a ranked list. The
existing tests covered the injection points and module-global isolation -- that
the primitives can be swapped -- but nothing about what it does with the results.

The scoping assertions matter most: this runs on the live retrieval path, and
`allowed_sources` is checked again here on every hit that comes back.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.retrievers.hybrid import candidate_collection


@dataclass
class _Doc:
    page_content: str
    metadata: dict


class _Settings:
    hybrid_rrf_k = 60
    reranker_top_n = 5
    hybrid_vector_weight = 0.5
    hybrid_bm25_weight = 0.5
    query_rewrite_enabled = False
    query_rewrite_with_llm = False
    query_decompose_enabled = False
    query_rewrite_max_variants = 6
    rank_feature_enabled = False


@dataclass
class _Retrieval:
    """The primitives collect_candidates is given, and a record of how it used them."""

    variants: list[str] = field(default_factory=list)
    vector: dict[str, list] = field(default_factory=dict)
    bm25: dict[str, list] = field(default_factory=dict)
    vector_calls: list[tuple[str, int]] = field(default_factory=list)
    bm25_calls: list[tuple[str, int]] = field(default_factory=list)

    def rewrite_fn(self, query, **_kwargs):
        return list(self.variants) or [query]

    def vector_fn(self, query, k, allowed_sources=None):
        self.vector_calls.append((query, k))
        return list(self.vector.get(query, ()))

    def bm25_fn(self, query, k, allowed_sources=None):
        self.bm25_calls.append((query, k))
        return list(self.bm25.get(query, ()))


def _collect(retrieval: _Retrieval, *, allowed_sources=None, threshold=0.2, settings=None, **kwargs):
    return candidate_collection.collect_candidates(
        "probe",
        allowed_sources=allowed_sources,
        vector_threshold=threshold,
        settings=settings or _Settings(),
        dynamic_top_k=4,
        rewrite_fn=retrieval.rewrite_fn,
        vector_fn=retrieval.vector_fn,
        bm25_fn=retrieval.bm25_fn,
        **kwargs,
    )


def _chunk(chunk_id: str, source: str = "a.pdf", text: str = "body") -> _Doc:
    return _Doc(page_content=text, metadata={"chunk_id": chunk_id, "source": source})


def test_variants_are_deduplicated_case_insensitively_in_order() -> None:
    retrieval = _Retrieval(variants=["Cost", "cost ", "latency", "COST"])

    _fused, diag = _collect(retrieval)

    assert diag["rewrites"] == ["Cost", "latency"]
    assert [query for query, _k in retrieval.vector_calls] == ["Cost", "latency"]


def test_a_rewrite_that_returns_nothing_falls_back_to_the_original_query() -> None:
    retrieval = _Retrieval(variants=[])

    _fused, diag = _collect(retrieval)

    assert diag["rewrites"] == ["probe"]


def test_vector_hits_below_the_threshold_are_dropped() -> None:
    retrieval = _Retrieval(variants=["probe"])
    retrieval.vector["probe"] = [(_chunk("c1"), 0.9), (_chunk("c2"), 0.1)]

    fused, diag = _collect(retrieval, threshold=0.5)

    assert [item["id"] for item in fused] == ["c1"]
    assert diag["vector_hits_by_rewrite"]["probe"] == 1


def test_a_hit_outside_the_allowed_sources_is_dropped_on_the_way_in() -> None:
    """The store scopes the search; this is the second check, on what came back."""

    retrieval = _Retrieval(variants=["probe"])
    retrieval.vector["probe"] = [(_chunk("mine", source="a.pdf"), 0.9), (_chunk("theirs", source="b.pdf"), 0.9)]
    retrieval.bm25["probe"] = [
        {"id": "sparse-mine", "text": "t", "metadata": {"source": "a.pdf"}, "bm25_score": 1.0},
        {"id": "sparse-theirs", "text": "t", "metadata": {"source": "b.pdf"}, "bm25_score": 1.0},
    ]

    fused, _diag = _collect(retrieval, allowed_sources=["a.pdf"])

    assert sorted(item["id"] for item in fused) == ["mine", "sparse-mine"]


def test_an_empty_allowed_list_admits_nothing_while_none_admits_everything() -> None:
    retrieval = _Retrieval(variants=["probe"])
    retrieval.vector["probe"] = [(_chunk("c1"), 0.9)]

    assert _collect(retrieval, allowed_sources=[])[0] == []
    assert [item["id"] for item in _collect(retrieval, allowed_sources=None)[0]] == ["c1"]


def test_precomputed_results_are_taken_as_already_filtered() -> None:
    retrieval = _Retrieval(variants=["probe"])

    fused, _diag = _collect(
        retrieval,
        threshold=0.5,
        precomputed_vector_results={"probe": [(_chunk("c1"), 0.1)]},
    )

    assert [item["id"] for item in fused] == ["c1"]  # below the threshold, and kept
    assert retrieval.vector_calls == []  # and the store was never asked


def test_precomputed_raw_results_are_filtered_before_use() -> None:
    retrieval = _Retrieval(variants=["probe"])

    fused, _diag = _collect(
        retrieval,
        threshold=0.5,
        precomputed_raw_vector_results={"probe": [(_chunk("c1"), 0.1), (_chunk("c2"), 0.9)]},
    )

    assert [item["id"] for item in fused] == ["c2"]
    assert retrieval.vector_calls == []


def test_a_chunk_found_by_two_variants_keeps_its_best_dense_score() -> None:
    retrieval = _Retrieval(variants=["one", "two"])
    retrieval.vector["one"] = [(_chunk("c1"), 0.4)]
    retrieval.vector["two"] = [(_chunk("c1"), 0.8)]

    fused, _diag = _collect(retrieval)

    assert len(fused) == 1
    assert fused[0]["dense_score"] == 0.8


def test_a_chunk_found_by_both_retrievers_records_both_and_keeps_the_best_bm25_score() -> None:
    retrieval = _Retrieval(variants=["one", "two"])
    retrieval.vector["one"] = [(_chunk("c1"), 0.9)]
    retrieval.bm25["one"] = [{"id": "c1", "text": "t", "metadata": {"source": "a.pdf"}, "bm25_score": 0.3}]
    retrieval.bm25["two"] = [{"id": "c1", "text": "t", "metadata": {"source": "a.pdf"}, "bm25_score": 0.7}]

    fused, _diag = _collect(retrieval)

    assert fused[0]["retrieval_sources"] == ["vector", "bm25"]
    assert fused[0]["bm25_score"] == 0.7


def test_results_are_ordered_by_fused_rank_and_a_score_buys_nothing() -> None:
    """RRF fuses on rank, not score: a BM25 score of 99 ranks exactly as rank 1.

    At equal weights the first vector hit and the first BM25 hit tie, and the
    second vector hit falls below both -- which is why a negative bm25_score is
    harmless here, and why a retriever cannot buy position with a large number.
    """

    retrieval = _Retrieval(variants=["probe"])
    retrieval.vector["probe"] = [(_chunk("first"), 0.9), (_chunk("second"), 0.9)]
    retrieval.bm25["probe"] = [{"id": "sparse", "text": "t", "metadata": {"source": "a.pdf"}, "bm25_score": 99.0}]

    fused, _diag = _collect(retrieval)

    assert [item["id"] for item in fused] == ["first", "sparse", "second"]
    assert fused[0]["hybrid_score"] == pytest.approx(fused[1]["hybrid_score"])
    assert fused[1]["hybrid_score"] > fused[2]["hybrid_score"]


def test_the_diagnostics_describe_the_search_that_ran() -> None:
    retrieval = _Retrieval(variants=["probe"])
    retrieval.vector["probe"] = [(_chunk("c1"), 0.9)]

    _fused, diag = _collect(retrieval)

    assert diag["vector_top_k"] == 4 and diag["bm25_top_k"] == 4  # from dynamic_top_k
    assert diag["dynamic_params_applied"] is True
    assert diag["reranker_top_n"] == 5  # from settings, not from dynamic_top_k
    assert diag["vector_weight"] == pytest.approx(0.5)
    assert diag["vector_threshold"] == pytest.approx(0.2)
    assert diag["candidate_count"] == 1


def test_the_rank_feature_score_is_added_to_the_fused_score_when_enabled() -> None:
    retrieval = _Retrieval(variants=["probe"])
    retrieval.vector["probe"] = [(_chunk("c1"), 0.9)]

    settings = _Settings()
    settings.rank_feature_enabled = True

    fused, _diag = _collect(retrieval, settings=settings)

    assert fused[0]["rank_feature_score"] > 0.0
    assert fused[0]["hybrid_score"] > fused[0]["rank_feature_score"]
