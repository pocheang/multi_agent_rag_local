"""Guard test: hybrid retrieval must not mutate module-level globals.

Two concurrent retrievals used to race on candidate_collection's module globals
(and on parent_expansion.get_parent_text_map): each call saved the "original",
installed its own, and restored in a finally block, so an interleaving could
leave the patched value installed permanently. This is a concurrent path --
RAGAgentService gathers query variants across a thread pool -- and the machinery
existed only for a test suite that was deleted on 2026-08-28.
"""

from __future__ import annotations

import inspect

from app.retrievers.hybrid import candidate_collection, parent_expansion, retriever


def test_retriever_source_has_no_global_assignment():
    source = inspect.getsource(retriever)
    for attr in ("build_rewrite_queries", "safe_similarity_search", "bm25_search"):
        assert f"candidate_collection.{attr} =" not in source, (
            f"retriever.py must not reassign candidate_collection.{attr}"
        )
    assert "parent_expansion.get_parent_text_map =" not in source


def test_collect_candidates_accepts_injected_callables():
    params = inspect.signature(candidate_collection.collect_candidates).parameters
    for name in ("rewrite_fn", "vector_fn", "bm25_fn"):
        assert name in params, f"collect_candidates must accept {name}"
        assert params[name].default is None
        assert params[name].kind is inspect.Parameter.KEYWORD_ONLY


def test_expand_to_parent_context_accepts_injected_lookup():
    params = inspect.signature(parent_expansion.expand_to_parent_context).parameters
    assert "parent_text_map_fn" in params
    assert params["parent_text_map_fn"].default is None
    assert params["parent_text_map_fn"].kind is inspect.Parameter.KEYWORD_ONLY


def test_injected_callables_are_actually_used():
    """Defaults must be overridable, otherwise the injection points are decoration."""
    calls: list[str] = []

    def fake_rewrite(query, **_kwargs):
        calls.append("rewrite")
        return [query]

    def fake_vector(_query, k, allowed_sources=None):
        calls.append("vector")
        return []

    def fake_bm25(_query, k, allowed_sources=None):
        calls.append("bm25")
        return []

    class _Settings:
        hybrid_rrf_k = 60
        reranker_top_n = 5
        query_rewrite_enabled = False
        query_rewrite_with_llm = False
        query_decompose_enabled = False
        query_rewrite_max_variants = 1

    candidate_collection.collect_candidates(
        "probe",
        allowed_sources=None,
        vector_threshold=0.2,
        settings=_Settings(),
        dynamic_top_k=4,
        rewrite_fn=fake_rewrite,
        vector_fn=fake_vector,
        bm25_fn=fake_bm25,
    )

    assert calls == ["rewrite", "vector", "bm25"]


def test_module_globals_survive_a_collect_call():
    before = (
        candidate_collection.build_rewrite_queries,
        candidate_collection.safe_similarity_search,
        candidate_collection.bm25_search,
        parent_expansion.get_parent_text_map,
    )

    retriever._collect_candidates_for_current_module(
        "probe",
        allowed_sources=["nonexistent-source"],
        vector_threshold=0.99,
        settings=type("S", (), {"hybrid_rrf_k": 60, "reranker_top_n": 5})(),
        dynamic_top_k=1,
    )

    after = (
        candidate_collection.build_rewrite_queries,
        candidate_collection.safe_similarity_search,
        candidate_collection.bm25_search,
        parent_expansion.get_parent_text_map,
    )
    assert before == after
