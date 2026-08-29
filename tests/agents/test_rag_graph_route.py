"""Regression test: a graph route must actually query the graph retriever.

The router maps route="graph" onto intent="knowledge_retrieval", but retrieval
gated the graph source on ``intent == "hybrid"``, so graph-routed queries
silently degraded to vector+BM25 and Neo4j was only ever reached via hybrid.
"""

from __future__ import annotations

import pytest

from app.agents.rag.service import RAGAgentService
from app.domain.contracts import EvidenceBundle, EvidenceItem, RouteDecision
from app.orchestration.request import OrchestrationRequest, RequestScope


def _request() -> OrchestrationRequest:
    """A request with a non-empty access scope.

    KnowledgeOrchestrator fails closed and skips every local source when the
    scope names neither documents nor sources, so an unscoped request would
    exercise the authorization guard instead of source selection.
    """
    return OrchestrationRequest(
        question="q",
        source_scope=RequestScope(allowed_sources=frozenset({"corpus"})),
    )


def _route(intent: str, route: str | None) -> RouteDecision:
    return RouteDecision(
        intent=intent,
        route=route,
        confidence=0.9,
        requires_plan=False,
        allowed_capabilities=frozenset({"rag"}),
        reason="test route",
    )


def _recorder(name: str, called: list[str]):
    """A retriever that records its own name and returns one usable item.

    Returning evidence (rather than an empty bundle) keeps the degradation
    policy satisfied, so the assertion under test is about source *selection*
    and not about retrieval failure handling.
    """

    async def retriever(request, decision, plan):
        called.append(name)
        return EvidenceBundle(
            items=(
                EvidenceItem(
                    content=f"{name} evidence for {request.question}",
                    source=f"{name}-source",
                    document_id=f"{name}-doc",
                    page=1,
                    retriever=name,
                ),
            )
        )

    return retriever


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("intent", "route", "graph_expected"),
    [
        ("knowledge_retrieval", "graph", True),
        ("hybrid", None, True),
        ("knowledge_retrieval", "vector", False),
        ("knowledge_retrieval", None, False),
    ],
)
async def test_graph_retriever_selected_for_graph_and_hybrid(intent, route, graph_expected):
    called: list[str] = []
    service = RAGAgentService(
        vector=_recorder("vector", called),
        bm25=_recorder("bm25", called),
        graph=_recorder("graph", called),
        web=_recorder("web", called),
    )

    await service.retrieve(_request(), _route(intent, route), None)

    assert ("graph" in called) is graph_expected


@pytest.mark.asyncio
async def test_vector_and_bm25_always_run():
    called: list[str] = []
    service = RAGAgentService(
        vector=_recorder("vector", called),
        bm25=_recorder("bm25", called),
        graph=_recorder("graph", called),
        web=_recorder("web", called),
    )

    await service.retrieve(_request(), _route("knowledge_retrieval", "graph"), None)

    assert "vector" in called
    assert "bm25" in called
