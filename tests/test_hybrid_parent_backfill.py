import importlib
import sys
import types
from types import SimpleNamespace
from app.services.resilience import TTLCache

def test_hybrid_search_backfills_parent_and_dedupes_by_parent(monkeypatch):
    fake_vector_store = types.ModuleType("app.retrievers.vector_store")
    fake_vector_store.similarity_search = lambda _q, k=None: []
    sys.modules["app.retrievers.vector_store"] = fake_vector_store

    hybrid_retriever = importlib.import_module("app.retrievers.hybrid_retriever")
    hybrid_retriever = importlib.reload(hybrid_retriever)

    class _Doc:
        def __init__(self, page_content: str, metadata: dict):
            self.page_content = page_content
            self.metadata = metadata

    monkeypatch.setattr(
        hybrid_retriever,
        "get_settings",
        lambda: SimpleNamespace(vector_top_k=5, bm25_top_k=5, hybrid_rrf_k=60, reranker_top_n=5),
    )

    vector_results = [
        (_Doc("child one", {"chunk_id": "c1", "source": "s1", "parent_id": "p1"}), 0.9),
        (_Doc("child two", {"chunk_id": "c2", "source": "s1", "parent_id": "p1"}), 0.8),
    ]
    monkeypatch.setattr(hybrid_retriever, "similarity_search", lambda _q, k=None: vector_results)
    monkeypatch.setattr(hybrid_retriever, "bm25_search", lambda _q, k=6, allowed_sources=None: [])
    monkeypatch.setattr(hybrid_retriever, "rerank", lambda _q, items, top_n=None: items)
    monkeypatch.setattr(hybrid_retriever, "get_parent_text_map", lambda _ids: {"p1": "parent block content"})

    result = hybrid_retriever.hybrid_search("test query")

    assert len(result) == 1
    assert result[0]["text"] == "parent block content"
    assert result[0]["child_text"] in {"child one", "child two"}
    assert result[0]["metadata"]["context_granularity"] == "parent"


def test_hybrid_search_relaxes_vector_threshold_when_strict_empty(monkeypatch):
    fake_vector_store = types.ModuleType("app.retrievers.vector_store")
    fake_vector_store.similarity_search = lambda _q, k=None: []
    sys.modules["app.retrievers.vector_store"] = fake_vector_store

    hybrid_retriever = importlib.import_module("app.retrievers.hybrid_retriever")
    hybrid_retriever = importlib.reload(hybrid_retriever)

    class _Doc:
        def __init__(self, page_content: str, metadata: dict):
            self.page_content = page_content
            self.metadata = metadata

    monkeypatch.setattr(
        hybrid_retriever,
        "get_settings",
        lambda: SimpleNamespace(
            vector_top_k=5,
            bm25_top_k=5,
            hybrid_rrf_k=60,
            reranker_top_n=5,
            hybrid_vector_weight=0.95,
            hybrid_bm25_weight=0.05,
            vector_similarity_threshold=0.8,
            vector_similarity_relaxed_threshold=0.05,
        ),
    )

    vector_results = [(_Doc("low but valid", {"chunk_id": "c-low", "source": "s1"}), 0.2)]
    monkeypatch.setattr(hybrid_retriever, "similarity_search", lambda _q, k=None: vector_results)
    monkeypatch.setattr(hybrid_retriever, "bm25_search", lambda _q, k=6, allowed_sources=None: [])
    monkeypatch.setattr(hybrid_retriever, "rerank", lambda _q, items, top_n=None: items)
    monkeypatch.setattr(hybrid_retriever, "get_parent_text_map", lambda _ids: {})

    result = hybrid_retriever.hybrid_search("test query")
    assert len(result) == 1
    assert result[0]["id"] == "c-low"


def test_hybrid_search_uses_query_variants(monkeypatch):
    fake_vector_store = types.ModuleType("app.retrievers.vector_store")
    fake_vector_store.similarity_search = lambda _q, k=None: []
    sys.modules["app.retrievers.vector_store"] = fake_vector_store

    hybrid_retriever = importlib.import_module("app.retrievers.hybrid_retriever")
    hybrid_retriever = importlib.reload(hybrid_retriever)

    class _Doc:
        def __init__(self, page_content: str, metadata: dict):
            self.page_content = page_content
            self.metadata = metadata

    seen_queries: list[str] = []

    def _fake_similarity_search(query: str, k=None):
        seen_queries.append(query)
        return [(_Doc("doc", {"chunk_id": "cid", "source": "s1"}), 0.9)]

    monkeypatch.setattr(
        hybrid_retriever,
        "get_settings",
        lambda: SimpleNamespace(
            vector_top_k=5,
            bm25_top_k=0,
            hybrid_rrf_k=60,
            reranker_top_n=5,
            hybrid_vector_weight=1.0,
            hybrid_bm25_weight=0.0,
            vector_similarity_threshold=0.1,
            vector_similarity_relaxed_threshold=0.05,
        ),
    )
    monkeypatch.setattr(hybrid_retriever, "similarity_search", _fake_similarity_search)
    monkeypatch.setattr(hybrid_retriever, "bm25_search", lambda _q, k=6, allowed_sources=None: [])
    monkeypatch.setattr(hybrid_retriever, "rerank", lambda _q, items, top_n=None: items)
    monkeypatch.setattr(hybrid_retriever, "get_parent_text_map", lambda _ids: {})

    result = hybrid_retriever.hybrid_search("Alpha Beta Gamma")
    assert result
    assert len(set(seen_queries)) >= 2


def test_hybrid_search_with_diagnostics_reports_rewrites_and_degrade(monkeypatch):
    fake_vector_store = types.ModuleType("app.retrievers.vector_store")
    fake_vector_store.similarity_search = lambda _q, k=None: []
    sys.modules["app.retrievers.vector_store"] = fake_vector_store

    hybrid_retriever = importlib.import_module("app.retrievers.hybrid_retriever")
    hybrid_retriever = importlib.reload(hybrid_retriever)

    class _Doc:
        def __init__(self, page_content: str, metadata: dict):
            self.page_content = page_content
            self.metadata = metadata

    monkeypatch.setattr(
        hybrid_retriever,
        "get_settings",
        lambda: SimpleNamespace(
            vector_top_k=5,
            bm25_top_k=0,
            hybrid_rrf_k=60,
            reranker_top_n=5,
            hybrid_vector_weight=1.0,
            hybrid_bm25_weight=0.0,
            vector_similarity_threshold=0.8,
            vector_similarity_relaxed_threshold=0.05,
            query_rewrite_enabled=True,
            query_rewrite_with_llm=False,
            query_decompose_enabled=True,
            query_rewrite_max_variants=6,
            rank_feature_enabled=False,
        ),
    )
    monkeypatch.setattr(hybrid_retriever, "similarity_search", lambda _q, k=None: [(_Doc("doc", {"chunk_id": "cid", "source": "s1.md"}), 0.2)])
    monkeypatch.setattr(hybrid_retriever, "bm25_search", lambda _q, k=6, allowed_sources=None: [])
    monkeypatch.setattr(hybrid_retriever, "rerank", lambda _q, items, top_n=None: items)
    monkeypatch.setattr(hybrid_retriever, "get_parent_text_map", lambda _ids: {})

    _result, diag = hybrid_retriever.hybrid_search_with_diagnostics("Alpha, Beta and Gamma")
    assert diag["degraded_to_relaxed_threshold"] is True
    assert len(diag["rewrites"]) >= 2


def test_hybrid_search_adds_rank_feature_score(monkeypatch):
    fake_vector_store = types.ModuleType("app.retrievers.vector_store")
    fake_vector_store.similarity_search = lambda _q, k=None: []
    sys.modules["app.retrievers.vector_store"] = fake_vector_store

    hybrid_retriever = importlib.import_module("app.retrievers.hybrid_retriever")
    hybrid_retriever = importlib.reload(hybrid_retriever)

    class _Doc:
        def __init__(self, page_content: str, metadata: dict):
            self.page_content = page_content
            self.metadata = metadata

    monkeypatch.setattr(
        hybrid_retriever,
        "get_settings",
        lambda: SimpleNamespace(
            vector_top_k=5,
            bm25_top_k=0,
            hybrid_rrf_k=60,
            reranker_top_n=5,
            hybrid_vector_weight=1.0,
            hybrid_bm25_weight=0.0,
            vector_similarity_threshold=0.1,
            vector_similarity_relaxed_threshold=0.05,
            query_rewrite_enabled=True,
            query_rewrite_with_llm=False,
            query_decompose_enabled=True,
            query_rewrite_max_variants=6,
            rank_feature_enabled=True,
            rank_feature_source_weight=0.1,
            rank_feature_freshness_weight=0.1,
            rank_feature_retrieval_diversity_weight=0.1,
        ),
    )
    monkeypatch.setattr(
        hybrid_retriever,
        "similarity_search",
        lambda _q, k=None: [(_Doc("doc", {"chunk_id": "cid", "source": "s1.md"}), 0.9)],
    )
    monkeypatch.setattr(hybrid_retriever, "bm25_search", lambda _q, k=6, allowed_sources=None: [])
    monkeypatch.setattr(hybrid_retriever, "rerank", lambda _q, items, top_n=None: items)
    monkeypatch.setattr(hybrid_retriever, "get_parent_text_map", lambda _ids: {})

    result = hybrid_retriever.hybrid_search("Alpha Beta")
    assert result
    assert "rank_feature_score" in result[0]
    assert result[0]["rank_feature_score"] > 0


def test_hybrid_search_enforces_allowed_sources_secondary_filter(monkeypatch):
    fake_vector_store = types.ModuleType("app.retrievers.vector_store")
    fake_vector_store.similarity_search = lambda _q, k=None, allowed_sources=None: []
    sys.modules["app.retrievers.vector_store"] = fake_vector_store

    hybrid_retriever = importlib.import_module("app.retrievers.hybrid_retriever")
    hybrid_retriever = importlib.reload(hybrid_retriever)

    class _Doc:
        def __init__(self, page_content: str, metadata: dict):
            self.page_content = page_content
            self.metadata = metadata

    monkeypatch.setattr(
        hybrid_retriever,
        "get_settings",
        lambda: SimpleNamespace(
            vector_top_k=5,
            bm25_top_k=5,
            hybrid_rrf_k=60,
            reranker_top_n=5,
            hybrid_vector_weight=1.0,
            hybrid_bm25_weight=0.0,
            vector_similarity_threshold=0.1,
            vector_similarity_relaxed_threshold=0.05,
            query_rewrite_enabled=True,
            query_rewrite_with_llm=False,
            query_decompose_enabled=False,
            query_rewrite_max_variants=4,
            rank_feature_enabled=False,
            retrieval_cache_enabled=False,
        ),
    )
    monkeypatch.setattr(
        hybrid_retriever,
        "similarity_search",
        lambda _q, k=None, allowed_sources=None: [(_Doc("doc", {"chunk_id": "cid", "source": "forbidden.md"}), 0.9)],
    )
    monkeypatch.setattr(hybrid_retriever, "bm25_search", lambda _q, k=6, allowed_sources=None: [])
    monkeypatch.setattr(hybrid_retriever, "rerank", lambda _q, items, top_n=None: items)
    monkeypatch.setattr(hybrid_retriever, "get_parent_text_map", lambda _ids: {})

    result = hybrid_retriever.hybrid_search("Alpha", allowed_sources=["allowed.md"])
    assert result == []


def test_hybrid_search_cache_hit(monkeypatch):
    fake_vector_store = types.ModuleType("app.retrievers.vector_store")
    fake_vector_store.similarity_search = lambda _q, k=None, allowed_sources=None: []
    sys.modules["app.retrievers.vector_store"] = fake_vector_store

    hybrid_retriever = importlib.import_module("app.retrievers.hybrid_retriever")
    hybrid_retriever = importlib.reload(hybrid_retriever)

    class _Doc:
        def __init__(self, page_content: str, metadata: dict):
            self.page_content = page_content
            self.metadata = metadata

    calls = {"n": 0}

    def _sim(_q, k=None, allowed_sources=None):
        calls["n"] += 1
        return [(_Doc("doc", {"chunk_id": "cid", "source": "s1.md"}), 0.9)]

    monkeypatch.setattr(
        hybrid_retriever,
        "get_settings",
        lambda: SimpleNamespace(
            vector_top_k=5,
            bm25_top_k=0,
            hybrid_rrf_k=60,
            reranker_top_n=5,
            hybrid_vector_weight=1.0,
            hybrid_bm25_weight=0.0,
            vector_similarity_threshold=0.1,
            vector_similarity_relaxed_threshold=0.05,
            query_rewrite_enabled=True,
            query_rewrite_with_llm=False,
            query_decompose_enabled=False,
            query_rewrite_max_variants=4,
            rank_feature_enabled=False,
            retrieval_cache_enabled=True,
            retrieval_cache_ttl_seconds=60,
            retrieval_cache_max_items=64,
            dynamic_retrieval_enabled=False,
        ),
    )
    monkeypatch.setattr(hybrid_retriever, "similarity_search", _sim)
    monkeypatch.setattr(hybrid_retriever, "bm25_search", lambda _q, k=6, allowed_sources=None: [])
    monkeypatch.setattr(hybrid_retriever, "rerank", lambda _q, items, top_n=None: items)
    monkeypatch.setattr(hybrid_retriever, "get_parent_text_map", lambda _ids: {})
    hybrid_retriever._RETRIEVAL_CACHE = TTLCache(ttl_seconds=60, max_items=64)

    _res1, d1 = hybrid_retriever.hybrid_search_with_diagnostics("cache query")
    _res2, d2 = hybrid_retriever.hybrid_search_with_diagnostics("cache query")
    assert calls["n"] == 1
    assert d1.get("cache_hit") is False
    assert d2.get("cache_hit") is True


def test_hybrid_search_baseline_strategy_reduces_variants(monkeypatch):
    fake_vector_store = types.ModuleType("app.retrievers.vector_store")
    fake_vector_store.similarity_search = lambda _q, k=None, allowed_sources=None: []
    sys.modules["app.retrievers.vector_store"] = fake_vector_store

    hybrid_retriever = importlib.import_module("app.retrievers.hybrid_retriever")
    hybrid_retriever = importlib.reload(hybrid_retriever)

    class _Doc:
        def __init__(self, page_content: str, metadata: dict):
            self.page_content = page_content
            self.metadata = metadata

    seen_queries: list[str] = []

    def _sim(q: str, k=None, allowed_sources=None):
        seen_queries.append(q)
        return [(_Doc("doc", {"chunk_id": "cid", "source": "s1.md"}), 0.9)]

    monkeypatch.setattr(
        hybrid_retriever,
        "get_settings",
        lambda: SimpleNamespace(
            vector_top_k=5,
            bm25_top_k=0,
            hybrid_rrf_k=60,
            reranker_top_n=5,
            hybrid_vector_weight=1.0,
            hybrid_bm25_weight=0.0,
            vector_similarity_threshold=0.1,
            vector_similarity_relaxed_threshold=0.05,
            query_rewrite_enabled=True,
            query_rewrite_with_llm=False,
            query_decompose_enabled=True,
            query_rewrite_max_variants=6,
            rank_feature_enabled=False,
            retrieval_cache_enabled=False,
            dynamic_retrieval_enabled=True,
            dynamic_vector_top_k_cap=16,
            dynamic_bm25_top_k_cap=16,
            dynamic_reranker_top_n_cap=10,
            retrieval_cache_backend="off",
        ),
    )
    monkeypatch.setattr(hybrid_retriever, "similarity_search", _sim)
    monkeypatch.setattr(hybrid_retriever, "bm25_search", lambda _q, k=6, allowed_sources=None: [])
    monkeypatch.setattr(hybrid_retriever, "rerank", lambda _q, items, top_n=None: items)
    monkeypatch.setattr(hybrid_retriever, "get_parent_text_map", lambda _ids: {})

    _res_adv, d_adv = hybrid_retriever.hybrid_search_with_diagnostics("Alpha, Beta and Gamma", retrieval_strategy="advanced")
    seen_adv = len(set(seen_queries))
    seen_queries.clear()
    _res_base, d_base = hybrid_retriever.hybrid_search_with_diagnostics("Alpha, Beta and Gamma", retrieval_strategy="baseline")
    seen_base = len(set(seen_queries))

    assert d_adv.get("strategy") == "advanced"
    assert d_base.get("strategy") == "baseline"
    assert seen_base <= seen_adv
