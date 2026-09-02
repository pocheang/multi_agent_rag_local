"""The graph route's vector fallback must carry the caller's identity.

`_run_basic_graph_rag` falls back to vector retrieval on two paths -- the graph
lookup raised, or it returned nothing -- and both called
`_fallback_to_vector_rag` without an owner, which the parameter's `= None`
default accepted silently. Neo4j is optional and an empty graph result is
routine, so this was the *common* path, and on it the store's own ownership
clause (`owner_user_id` / `visibility` / `tenant_id` on the chunk) was simply
absent: only the source filter narrowed the search.

`tests/security/test_no_unrestricted_retrieval.py` did not see it because the
call reaches `similarity_search` through four hops, each of which writes
`owner=owner` and so satisfies an AST check.
"""

from __future__ import annotations

import pytest

from app.agents.rag import graph as graph_module
from app.retrievers.stores.vector import OwnerScope

_OWNER = OwnerScope(user_id="alice", tenant_id="acme")


@pytest.fixture
def vector_calls(monkeypatch):
    """Capture what the graph route hands to the vector fallback."""
    calls: list[dict] = []

    def _record(question, allowed_sources=None, agent_class=None, *, owner):
        calls.append({"question": question, "allowed_sources": allowed_sources, "owner": owner})
        return {"context": "", "citations": [], "retrieved_count": 0, "effective_hit_count": 0}

    import app.agents.rag.vector as vector_module

    monkeypatch.setattr(vector_module, "run_vector_rag", _record)
    return calls


def test_fallback_after_a_graph_error_keeps_the_owner(monkeypatch, vector_calls):
    import app.tools.graph.core as graph_core

    def _explode(*_args, **_kwargs):
        raise RuntimeError("neo4j is down")

    monkeypatch.setattr(graph_core, "graph_lookup", _explode)

    graph_module.run_graph_rag("who owns x?", ["a.pdf"], owner=_OWNER)

    assert [call["owner"] for call in vector_calls] == [_OWNER]


def test_fallback_after_an_empty_graph_result_keeps_the_owner(monkeypatch, vector_calls):
    import app.tools.graph.core as graph_core

    monkeypatch.setattr(
        graph_core,
        "graph_lookup",
        lambda *_args, **_kwargs: {"entities": [], "neighbors": [], "paths": [], "graph_signal_score": 0.0},
    )

    graph_module.run_graph_rag("who owns x?", ["a.pdf"], owner=_OWNER)

    assert [call["owner"] for call in vector_calls] == [_OWNER]


def test_the_fallback_cannot_be_called_without_an_owner():
    """The `= None` default is what made the leak silent; it must stay gone."""
    with pytest.raises(TypeError, match="owner"):
        graph_module._fallback_to_vector_rag("q", ["a.pdf"], "empty_results")


def test_the_graph_entry_point_cannot_be_called_without_an_owner():
    with pytest.raises(TypeError, match="owner"):
        graph_module.run_graph_rag("q", ["a.pdf"])
