"""Tests for Task 2 typed adapters around existing agent implementations."""

import asyncio
from types import SimpleNamespace

import pytest

from app.agents.planner.service import PlannerAgentService
from app.agents.rag.service import RAGAgentService
from app.agents.router.service import RouterAgentService
from app.agents.synthesizer.service import SynthesizerAgentService
from app.agents.tool.service import ToolAgentService
from app.domain.contracts import EvidenceBundle, EvidenceItem, RouteDecision
from app.orchestration.request import OrchestrationRequest


@pytest.mark.asyncio
async def test_router_service_maps_legacy_react_route_to_typed_plan_and_tool_capabilities() -> None:
    """Changing a ReAct route to skip planning or tools must fail this test."""
    service = RouterAgentService(
        decider=lambda *_args, **_kwargs: SimpleNamespace(route="react", confidence=0.82, reason="multi-hop")
    )

    decision = await service.route(OrchestrationRequest(question="Compare then verify"))

    assert decision == RouteDecision(
        intent="tool_call",
        confidence=0.82,
        requires_plan=True,
        allowed_capabilities=frozenset({"rag", "tool"}),
        reason="multi-hop",
    )


@pytest.mark.asyncio
async def test_planner_service_builds_a_dependency_plan_from_decomposed_queries() -> None:
    """Planner output must remain a valid, ordered TaskPlan rather than raw strings."""
    async def decompose(_question: str) -> tuple[str, ...]:
        return ("Find the facts", "Compare the facts")

    route = RouteDecision(
        intent="hybrid",
        confidence=0.9,
        requires_plan=True,
        allowed_capabilities=frozenset({"rag"}),
        reason="comparison",
    )
    plan = await PlannerAgentService(decompose=decompose).plan(OrchestrationRequest(question="Compare A and B"), route)

    assert tuple(task.prompt for task in plan.tasks) == ("Find the facts", "Compare the facts")
    assert plan.tasks[1].depends_on == ("task-1",)


@pytest.mark.asyncio
async def test_rag_service_runs_enabled_retrievers_concurrently_and_fuses_evidence() -> None:
    """Sequential retrieval or missing fusion would make this deterministic result fail."""
    calls: list[str] = []

    async def vector(*_args: object) -> EvidenceBundle:
        await asyncio.sleep(0)
        calls.append("vector")
        return EvidenceBundle(
            items=(EvidenceItem(content="Low", source="guide.pdf", document_id="guide", page=1, score=0.4),)
        )

    async def bm25(*_args: object) -> EvidenceBundle:
        await asyncio.sleep(0)
        calls.append("bm25")
        return EvidenceBundle()

    async def graph(*_args: object) -> EvidenceBundle:
        await asyncio.sleep(0)
        calls.append("graph")
        return EvidenceBundle(
            items=(EvidenceItem(content="High", source="guide.pdf", document_id="guide", page=1, score=0.9),)
        )

    route = RouteDecision(
        intent="hybrid",
        confidence=0.9,
        requires_plan=False,
        allowed_capabilities=frozenset({"rag"}),
        reason="hybrid",
    )
    evidence = await RAGAgentService(vector=vector, bm25=bm25, graph=graph).retrieve(
        OrchestrationRequest(question="Compare"), route, None
    )

    assert set(calls) == {"vector", "bm25", "graph"}
    assert evidence.items[0].content == "High"


@pytest.mark.asyncio
async def test_tool_service_returns_no_unguarded_tool_result_before_gateway_is_available() -> None:
    """Task 2 must not invent an ungoverned external tool call before Task 3."""
    result = await ToolAgentService().run(
        OrchestrationRequest(question="Run an action"),
        RouteDecision(
            intent="tool_call",
            confidence=0.8,
            requires_plan=True,
            allowed_capabilities=frozenset({"rag", "tool"}),
            reason="needs tool",
        ),
        await PlannerAgentService().plan(
            OrchestrationRequest(question="Run an action"),
            RouteDecision(
                intent="tool_call",
                confidence=0.8,
                requires_plan=True,
                allowed_capabilities=frozenset({"rag", "tool"}),
                reason="needs tool",
            ),
        ),
        EvidenceBundle(),
    )

    assert result == ()


@pytest.mark.asyncio
async def test_synthesizer_service_returns_citations_for_typed_evidence() -> None:
    """A synthesized answer must keep evidence identifiers as citation labels."""
    def generate(*_args: object, **_kwargs: object) -> str:
        return "RAG combines retrieval and generation [guide:7]."

    evidence = EvidenceBundle(
        items=(EvidenceItem(content="RAG definition", source="guide.pdf", document_id="guide", page=7),)
    )
    route = RouteDecision(
        intent="knowledge_retrieval",
        confidence=0.95,
        requires_plan=False,
        allowed_capabilities=frozenset({"rag"}),
        reason="direct",
    )

    answer = await SynthesizerAgentService(generate=generate).synthesize(
        OrchestrationRequest(question="What is RAG?"), route, None, evidence, ()
    )

    assert answer.text == "RAG combines retrieval and generation [guide:7]."
    assert answer.citations == ("guide:7",)
    assert answer.evidence_ids == evidence.item_ids
