"""`GRAPH_RAG_ENHANCED` has to actually select the enhanced lookup.

`_run_graph_rag_impl` gated the enhanced branch on `should_enhance and
retrieved_docs`. The setting was therefore inert: the one production caller
(`app/knowledge/adapters.py`) reached `run_graph_rag` with no documents, so every
request fell through to `graph_lookup`, and all 495 lines of
`app/agents/rag/enhanced_graph.py` were dead code that the module graph
nonetheless said was reachable.

Documents are a *refinement* of that branch, not its precondition: they feed the
quality estimate that picks the result limits, and the estimate has a defined
neutral value without them.
"""

from __future__ import annotations

import pytest

from app.agents.rag import graph as graph_module
from app.retrievers.stores.vector import OwnerScope

_OWNER = OwnerScope(user_id="alice", tenant_id="acme")
_HIT = {
    "entities": [{"entity": "Q3 Revenue", "relations": []}],
    "neighbors": [],
    "paths": [],
    "graph_signal_score": 0.8,
    "confidence": "high",
}

_STRUCTURED_DOC = {
    # Headers, a list and enough prose to score as a good source document.
    "content": "# Q3 Results\n\n- Revenue rose 12 percent year over year.\n" + ("Revenue analysis. " * 200),
    "metadata": {"page": 1, "total_pages": 40, "format": "markdown"},
}


@pytest.fixture
def lookups(monkeypatch):
    """Record which of the two graph lookups the request reached."""
    calls: dict[str, list] = {"basic": [], "enhanced": []}

    import app.agents.rag.enhanced_graph as enhanced_module
    import app.tools.graph.core as graph_core

    monkeypatch.setattr(graph_core, "graph_lookup", lambda *a, **k: (calls["basic"].append(k), _HIT)[1])
    monkeypatch.setattr(
        enhanced_module,
        "graph_lookup_enhanced",
        lambda **kwargs: (calls["enhanced"].append(kwargs), _HIT)[1],
    )
    return calls


def test_enhanced_mode_reaches_the_enhanced_lookup_without_documents(monkeypatch, lookups):
    monkeypatch.setattr(graph_module.get_settings(), "graph_rag_enhanced", True, raising=False)

    graph_module.run_graph_rag("what drove q3 revenue?", ["a.pdf"], owner=_OWNER)

    assert lookups["enhanced"], "GRAPH_RAG_ENHANCED=true still fell through to the basic lookup"
    assert not lookups["basic"]


def test_without_documents_quality_falls_to_the_neutral_estimate(monkeypatch, lookups):
    """No documents is 'unknown quality', not 'bad quality': the limits must be
    the medium ones, and the low-quality skip must not fire."""
    from app.agents.rag.config import GRAPH_PARAMS_MEDIUM_QUALITY

    monkeypatch.setattr(graph_module.get_settings(), "graph_rag_enhanced", True, raising=False)

    graph_module.run_graph_rag("what drove q3 revenue?", ["a.pdf"], owner=_OWNER)

    call = lookups["enhanced"][0]
    assert call["context_quality"] == pytest.approx(0.5)
    assert call["max_entities"] == GRAPH_PARAMS_MEDIUM_QUALITY["max_entities"]


def test_documents_widen_the_limits_when_they_are_good(monkeypatch, lookups):
    """The point of the second retrieval phase: a well-structured corpus is
    evidence that the graph built from it is worth searching harder."""
    monkeypatch.setattr(graph_module.get_settings(), "graph_rag_enhanced", True, raising=False)

    graph_module.run_graph_rag(
        "what drove q3 revenue?",
        ["a.pdf"],
        None,
        [_STRUCTURED_DOC],
        None,
        owner=_OWNER,
    )

    call = lookups["enhanced"][0]
    assert call["context_quality"] > 0.5
    assert call["max_entities"] >= 10


def test_enhanced_mode_off_keeps_the_basic_lookup(monkeypatch, lookups):
    monkeypatch.setattr(graph_module.get_settings(), "graph_rag_enhanced", False, raising=False)

    graph_module.run_graph_rag("what drove q3 revenue?", ["a.pdf"], owner=_OWNER)

    assert lookups["basic"]
    assert not lookups["enhanced"]


def test_a_low_quality_corpus_skips_the_graph_and_falls_back(monkeypatch, lookups):
    """Skipping is not returning nothing: `GraphRetrievalService` treats an empty
    graph result as a reason to fall back to vector, so the answer survives."""
    import app.agents.rag.vector as vector_module

    fallbacks: list[str] = []
    monkeypatch.setattr(graph_module.get_settings(), "graph_rag_enhanced", True, raising=False)
    monkeypatch.setattr(graph_module.get_settings(), "graph_rag_min_pdf_quality", 0.9, raising=False)
    monkeypatch.setattr(
        vector_module,
        "run_vector_rag",
        lambda question, allowed_sources=None, agent_class=None, *, owner: (
            fallbacks.append(question),
            {"context": "vector answer", "citations": [], "retrieved_count": 1, "effective_hit_count": 1},
        )[1],
    )

    result = graph_module.run_graph_rag(
        "what drove q3 revenue?",
        ["a.pdf"],
        None,
        [{"content": "scan artifact", "metadata": {}}],
        None,
        owner=_OWNER,
    )

    assert not lookups["enhanced"], "the graph was searched despite a corpus below the quality floor"
    assert fallbacks, "skipping the graph must fall back to vector, not return nothing"
    assert result.get("skipped_reason") == "low_quality_documents"
