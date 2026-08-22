"""Behavioral coverage for the optional planning and tool stages."""

from dataclasses import dataclass, field

import pytest

from app.domain.contracts import (
    EvidenceBundle,
    EvidenceItem,
    FinalAnswer,
    PlannedTask,
    RouteDecision,
    TaskPlan,
    ToolResult,
)
from app.orchestration.engine import OrchestrationEngine, OrchestrationServices
from app.orchestration.event_publisher import InMemoryEventPublisher
from app.orchestration.request import OrchestrationRequest


@dataclass
class CallLog:
    calls: list[str] = field(default_factory=list)


@pytest.mark.asyncio
async def test_complex_question_runs_plan_and_governed_tool_before_synthesis() -> None:
    """Removing either optional-stage policy branch must fail this trace-level test."""
    log = CallLog()

    async def route(_request: OrchestrationRequest) -> RouteDecision:
        log.calls.append("route")
        return RouteDecision(
            intent="tool_call",
            confidence=0.89,
            requires_plan=True,
            allowed_capabilities=frozenset({"rag", "tool"}),
            reason="The answer needs governed lookup.",
        )

    async def plan(_request: OrchestrationRequest, _route: RouteDecision) -> TaskPlan:
        log.calls.append("plan")
        return TaskPlan(tasks=(PlannedTask(task_id="lookup", prompt="Find the record", tool_required=True),))

    async def retrieve(
        _request: OrchestrationRequest,
        _route: RouteDecision,
        _plan: TaskPlan | None,
    ) -> EvidenceBundle:
        log.calls.append("rag")
        return EvidenceBundle(items=(EvidenceItem(content="Record exists", source="records", document_id="r-1"),))

    async def run_tool(
        _request: OrchestrationRequest,
        _route: RouteDecision,
        plan_value: TaskPlan,
        evidence: EvidenceBundle,
    ) -> tuple[ToolResult, ...]:
        log.calls.append("tool")
        assert plan_value.requires_tools is True
        assert evidence.items[0].document_id == "r-1"
        return (ToolResult(tool_id="querymind_rag_search_evidence", status="succeeded", summary="Found record"),)

    async def synthesize(
        _request: OrchestrationRequest,
        route_decision: RouteDecision,
        _plan: TaskPlan | None,
        evidence: EvidenceBundle,
        tool_results: tuple[ToolResult, ...],
    ) -> FinalAnswer:
        log.calls.append("synthesize")
        assert tool_results[0].status == "succeeded"
        return FinalAnswer(answer="Record exists [r-1]", route=route_decision, evidence_ids=evidence.item_ids)

    publisher = InMemoryEventPublisher()
    engine = OrchestrationEngine(
        services=OrchestrationServices(
            router=route,
            planner=plan,
            retriever=retrieve,
            tool_runner=run_tool,
            synthesizer=synthesize,
        ),
        publisher=publisher,
    )

    answer = await engine.execute(OrchestrationRequest(question="Find the record and verify it"))

    assert answer.text == "Record exists [r-1]"
    assert log.calls == ["route", "plan", "rag", "tool", "synthesize"]
    assert [event.stage for event in publisher.events] == ["route", "plan", "rag", "tool", "synthesize", "complete"]
