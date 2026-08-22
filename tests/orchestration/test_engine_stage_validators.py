"""Regression coverage for every runtime-validated engine stage boundary."""

import pytest

from app.domain.contracts import EvidenceBundle, FinalAnswer, PlannedTask, RouteDecision, TaskPlan, ToolResult
from app.domain.errors import StageExecutionError
from app.orchestration.engine import OrchestrationEngine, OrchestrationServices
from app.orchestration.request import OrchestrationRequest


def _route(*, requires_plan: bool = False, allows_tool: bool = False) -> RouteDecision:
    capabilities = {"rag"}
    if allows_tool:
        capabilities.add("tool")
    return RouteDecision(
        intent="tool_call" if allows_tool else "knowledge_retrieval",
        confidence=0.9,
        requires_plan=requires_plan,
        allowed_capabilities=frozenset(capabilities),
        reason="Test route.",
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid_stage", ["route", "plan", "tool", "synthesize"])
async def test_engine_rejects_invalid_output_at_each_remaining_stage(invalid_stage: str) -> None:
    """Each validator must stop arbitrary objects at the boundary that produced them."""
    async def route(_request: OrchestrationRequest) -> RouteDecision:
        if invalid_stage == "route":
            return object()  # type: ignore[return-value]
        return _route(requires_plan=invalid_stage in {"plan", "tool"}, allows_tool=invalid_stage == "tool")

    async def plan(_request: OrchestrationRequest, _route_decision: RouteDecision) -> TaskPlan:
        if invalid_stage == "plan":
            return object()  # type: ignore[return-value]
        return TaskPlan(tasks=(PlannedTask(task_id="lookup", prompt="Lookup", tool_required=invalid_stage == "tool"),))

    async def retrieve(
        _request: OrchestrationRequest,
        _route_decision: RouteDecision,
        _plan: TaskPlan | None,
    ) -> EvidenceBundle:
        return EvidenceBundle()

    async def tools(
        _request: OrchestrationRequest,
        _route_decision: RouteDecision,
        _plan: TaskPlan,
        _evidence: EvidenceBundle,
    ) -> tuple[ToolResult, ...]:
        if invalid_stage == "tool":
            return (object(),)  # type: ignore[return-value]
        return ()

    async def synthesize(
        _request: OrchestrationRequest,
        route_decision: RouteDecision,
        _plan: TaskPlan | None,
        _evidence: EvidenceBundle,
        _tool_results: tuple[ToolResult, ...],
    ) -> FinalAnswer:
        if invalid_stage == "synthesize":
            return object()  # type: ignore[return-value]
        return FinalAnswer(answer="Answer", route=route_decision)

    engine = OrchestrationEngine(
        services=OrchestrationServices(
            router=route,
            planner=plan,
            retriever=retrieve,
            tool_runner=tools,
            synthesizer=synthesize,
        )
    )

    with pytest.raises(StageExecutionError, match=rf"stage '{invalid_stage}' failed"):
        await engine.execute(OrchestrationRequest(question="Test"))
