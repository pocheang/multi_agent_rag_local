from types import SimpleNamespace

import app.agents.rag.graph as graph_rag_agent
import app.agents.rag.vector as vector_rag_agent
from app.services.agent_document_filter import get_sources_by_agent_class


def test_specialist_agent_without_labeled_documents_returns_empty_scope(monkeypatch):
    monkeypatch.setattr("app.services.agent_document_filter.read_corpus_records", lambda: [])

    assert get_sources_by_agent_class("cybersecurity") == []
    assert get_sources_by_agent_class("general") is None


def test_vector_rag_intersects_explicit_scope_with_agent_class(monkeypatch):
    seen = {}

    monkeypatch.setattr(vector_rag_agent, "get_settings", lambda: SimpleNamespace(max_context_chunks=3))
    monkeypatch.setattr(vector_rag_agent, "get_sources_by_agent_class", lambda _agent: ["doc2.md", "doc3.md"])

    def fake_search(question, allowed_sources=None, retrieval_strategy=None):
        seen["allowed_sources"] = allowed_sources
        return [], {}

    monkeypatch.setattr(vector_rag_agent, "hybrid_search_with_diagnostics", fake_search)

    vector_rag_agent.run_vector_rag(
        "scope test",
        allowed_sources=["doc1.md", "doc2.md"],
        agent_class="cybersecurity",
    )

    assert seen["allowed_sources"] == ["doc2.md"]


def test_graph_rag_intersects_explicit_scope_with_agent_class(monkeypatch):
    seen = {}

    monkeypatch.setattr(graph_rag_agent, "get_settings", lambda: SimpleNamespace(graph_rag_enhanced=False))
    monkeypatch.setattr(graph_rag_agent, "get_sources_by_agent_class", lambda _agent: ["doc2.md"])

    def fake_graph_lookup(question, allowed_sources=None):
        seen["allowed_sources"] = allowed_sources
        return {
            "entities": [],
            "neighbors": [],
            "paths": [],
            "graph_signal_score": 0.0,
        }

    monkeypatch.setattr("app.tools.graph_tools.graph_lookup", fake_graph_lookup)

    graph_rag_agent.run_graph_rag(
        "scope test",
        allowed_sources=["doc1.md", "doc2.md"],
        agent_class="cybersecurity",
    )

    assert seen["allowed_sources"] == ["doc2.md"]
