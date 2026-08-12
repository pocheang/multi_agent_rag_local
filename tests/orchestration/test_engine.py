"""Behavioral tests for the typed route-to-answer orchestration engine."""

from dataclasses import dataclass, field

import pytest

from app.domain.contracts import EvidenceBundle, EvidenceItem, FinalAnswer, RouteDecision
from app.orchestration.engine import OrchestrationEngine, OrchestrationServices
from app.orchestration.event_publisher import InMemoryEventPublisher
from app.orchestration.request import OrchestrationRequest


@dataclass
class CallLog:
    calls: list[str] = field(default_factory=list)


@pytest.mark.asyncio
async def test_simple_question_skips_planner_and_tool_execution() -> None:
    """Changing the simple-route policy to invoke Planner or Tool must fail this test."""
    log = CallLog()

    async def route(_request: OrchestrationRequest) -> RouteDecision:
        log.calls.append("route")
        return RouteDecision(
            intent="knowledge_retrieval",
            confidence=0.95,
            requires_plan=False,
            allowed_capabilities=frozenset({"rag"}),
            reason="Direct lookup.",
        )

    async def retrieve(
        _request: OrchestrationRequest,
        _route: RouteDecision,
        _plan: object | None,
    ) -> EvidenceBundle:
        log.calls.append("rag")
        return EvidenceBundle(items=(EvidenceItem(content="Source fact", source="guide.md", document_id="guide"),))

    async def synthesize(
        _request: OrchestrationRequest,
        route_decision: RouteDecision,
        _plan: object | None,
        evidence: EvidenceBundle,
        _tool_results: tuple[object, ...],
    ) -> FinalAnswer:
        log.calls.append("synthesize")
        return FinalAnswer(
            text="Source fact [guide]",
            citations=("guide",),
            route=route_decision,
            evidence_ids=evidence.item_ids,
        )

    async def forbidden_planner(*_args: object) -> object:
        raise AssertionError("simple requests must not await Planner")

    async def forbidden_tool(*_args: object) -> tuple[object, ...]:
        raise AssertionError("simple requests must not await Tool")

    publisher = InMemoryEventPublisher()
    engine = OrchestrationEngine(
        services=OrchestrationServices(
            router=route,
            planner=forbidden_planner,
            retriever=retrieve,
            tool_runner=forbidden_tool,
            synthesizer=synthesize,
        ),
        publisher=publisher,
    )

    answer = await engine.execute(OrchestrationRequest(question="What is RAG?"))

    assert answer.text == "Source fact [guide]"
    assert log.calls == ["route", "rag", "synthesize"]
    assert [event.stage for event in publisher.events] == ["route", "rag", "synthesize", "complete"]
