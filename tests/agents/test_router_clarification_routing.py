"""Needing to ask a question must not decide what to retrieve.

`RouterAgentService` used to return early with `route="clarification"` the moment
`assess_completeness` found a missing field -- before the LLM router ran at all.
The completeness rules fire on anything comparison-shaped ("A 和 B 的区别"), and
the substitute route carried `allowed_capabilities={"rag"}` and no graph or web
hint, so those questions were answered from vector+BM25 with the graph and the
web silently excluded.

That mattered most where it was least visible: interactive clarification cannot
happen inside the pipeline, so the run continued with the original question --
now on a route nothing had chosen for it. Skipping clarification in the UI took
the same path.

The two decisions are separate now: `route` stays whatever the router picked and
`clarification_fields` carries what is missing.
"""

from __future__ import annotations

import pytest

from app.agents.router.routing import LegacyRouteDecision
from app.agents.router.service import RouterAgentService
from app.orchestration.request import OrchestrationRequest

_COMPARISON = "比较一下这两个方案"  # comparison-shaped, no extractable targets


def _router(route: str = "graph") -> RouterAgentService:
    def _decide(*_args, **_kwargs) -> LegacyRouteDecision:
        return LegacyRouteDecision(
            route=route,
            reason="llm_decision",
            skill="answer_with_citations",
            agent_class="general",
            confidence=0.82,
            raw_confidence=0.9,
        )

    return RouterAgentService(decider=_decide)


@pytest.mark.asyncio
async def test_a_clarifiable_question_keeps_the_route_the_router_chose():
    decision = await _router("graph").route(OrchestrationRequest(question=_COMPARISON))

    assert decision.route == "graph"
    assert decision.clarification_fields == ("doc_ids",)


@pytest.mark.asyncio
async def test_a_clarifiable_question_keeps_its_retrieval_capabilities():
    """`allowed_capabilities={"rag"}` on the substitute route is what removed web."""
    decision = await _router("web").route(OrchestrationRequest(question=_COMPARISON))

    assert "web" in decision.allowed_capabilities


@pytest.mark.asyncio
async def test_the_missing_fields_still_reach_the_clarification_stage():
    from app.orchestration.langgraph.nodes import _knowledge_hints

    decision = await _router("graph").route(OrchestrationRequest(question=_COMPARISON))

    assert decision.clarification_fields
    # And the route still translates into the sources it implies.
    assert "graph" in _knowledge_hints(decision)


@pytest.mark.asyncio
async def test_a_complete_question_carries_no_clarification_fields():
    decision = await _router("vector").route(OrchestrationRequest(question="总结这份季度报告"))

    assert decision.clarification_fields == ()
    assert decision.route == "vector"


@pytest.mark.asyncio
async def test_a_clarifiable_question_is_planned_for():
    decision = await _router("vector").route(OrchestrationRequest(question=_COMPARISON))

    assert decision.requires_plan is True


@pytest.mark.asyncio
async def test_the_reason_records_both_decisions():
    decision = await _router("graph").route(OrchestrationRequest(question=_COMPARISON))

    assert "llm_decision" in decision.reason
    assert "missing_required_information:doc_ids" in decision.reason


def test_clarification_is_no_longer_a_route_the_policy_accepts():
    """It never described retrieval, so it has no business in the route set."""
    from app.orchestration.policies import ExecutionPolicy

    assert "clarification" not in ExecutionPolicy().allowed_routes
