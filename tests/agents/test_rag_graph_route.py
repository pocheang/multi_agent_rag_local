"""The `graph` and `hybrid` routes must actually reach the graph.

The graph route degraded silently to vector+BM25 twice, for two different
reasons. First the retriever ignored the route. Then, after selection moved to
the Knowledge Agent, the Agent consulted only relationship *keywords* -- so
"graph" as a routing decision meant nothing unless the user's wording happened
to contain 关系/dependency/graph.

The route is an instruction. These tests pin that the Knowledge Agent treats it
as one, and that `_knowledge_hints` translates each route into the sources it
implies.
"""

from __future__ import annotations

import pytest

from app.agents.knowledge.service import KnowledgeAgentService
from app.domain.contracts import RouteDecision
from app.domain.workflow import RouterDecision
from app.orchestration.langgraph.nodes import _knowledge_hints
from app.orchestration.request import OrchestrationRequest


def _decision(*hints: str) -> RouterDecision:
    return RouterDecision(
        intent="knowledge_retrieval",
        complexity="simple",
        completeness="complete",
        next_stage="knowledge",
        knowledge_hints=frozenset(hints),
        confidence=0.9,
        reason="test",
    )


def _request(question: str = "summarise the quarterly report", **overrides) -> OrchestrationRequest:
    return OrchestrationRequest(**{"question": question, **overrides})


async def _sources(*hints: str, question: str = "summarise the quarterly report", **overrides) -> set[str]:
    strategy = await KnowledgeAgentService().decide(_request(question, **overrides), _decision(*hints), None)
    return {plan.source for plan in strategy.sources}


# --- the route decides -------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.parametrize("route", ["graph", "hybrid"])
async def test_the_graph_joins_on_its_own_routes_whatever_the_wording(route):
    """Neutral wording, no relationship keyword: the route alone must carry it."""
    hints = _knowledge_hints(RouteDecision(route=route, confidence=1.0, requires_plan=False, reason="t"))

    assert "graph" in await _sources(*hints)


@pytest.mark.asyncio
async def test_the_graph_stays_out_of_the_vector_route():
    hints = _knowledge_hints(RouteDecision(route="vector", confidence=1.0, requires_plan=False, reason="t"))

    assert "graph" not in await _sources(*hints)


@pytest.mark.asyncio
async def test_relationship_wording_still_reaches_the_graph_on_any_route():
    assert "graph" in await _sources("vector", "bm25", question="X 和 Y 的依赖关系是什么")


@pytest.mark.asyncio
async def test_vector_and_bm25_always_run():
    assert {"vector", "bm25"} <= await _sources("vector", "bm25")


# --- web: two different authorizations ---------------------------------------


@pytest.mark.asyncio
async def test_the_web_route_searches_the_web_without_the_fallback_flag():
    """`use_web_fallback` defaults to False on every chat request. Requiring it
    here is what removed web search from the web route itself."""
    hints = _knowledge_hints(RouteDecision(route="web", confidence=1.0, requires_plan=False, reason="t"))

    assert "web" in await _sources(*hints, use_web_fallback=False)


@pytest.mark.asyncio
async def test_the_fallback_flag_adds_freshness_web_on_other_routes():
    assert "web" in await _sources("vector", "bm25", question="今天的最新新闻", use_web_fallback=True)


@pytest.mark.asyncio
async def test_without_the_flag_freshness_wording_alone_does_not_reach_the_web():
    assert "web" not in await _sources("vector", "bm25", question="今天的最新新闻", use_web_fallback=False)


# --- the hint map ------------------------------------------------------------


@pytest.mark.asyncio
async def test_every_route_hints_at_the_local_pair():
    for route in ("vector", "graph", "hybrid", "web", "react"):
        hints = _knowledge_hints(RouteDecision(route=route, confidence=1.0, requires_plan=False, reason="t"))
        assert {"vector", "bm25"} <= hints, route
