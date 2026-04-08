import importlib
import sys
import types
from types import SimpleNamespace

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
    monkeypatch.setattr(hybrid_retriever, "bm25_search", lambda _q, k=6: [])
    monkeypatch.setattr(hybrid_retriever, "rerank", lambda _q, items, top_n=None: items)
    monkeypatch.setattr(hybrid_retriever, "get_parent_text_map", lambda _ids: {"p1": "parent block content"})

    result = hybrid_retriever.hybrid_search("test query")

    assert len(result) == 1
    assert result[0]["text"] == "parent block content"
    assert result[0]["child_text"] in {"child one", "child two"}
    assert result[0]["metadata"]["context_granularity"] == "parent"
