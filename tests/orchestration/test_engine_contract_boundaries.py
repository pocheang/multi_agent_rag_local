"""Tests that stage outputs cannot cross orchestration boundaries unvalidated."""

import pytest

from app.domain.contracts import EvidenceBundle, FinalAnswer, RouteDecision, TaskPlan, ToolResult
from app.domain.errors import StageExecutionError
from app.orchestration.engine import OrchestrationEngine, OrchestrationServices
from app.orchestration.request import OrchestrationRequest


@pytest.mark.asyncio
async def test_engine_rejects_invalid_retriever_result_at_rag_boundary() -> None:
    """Replacing EvidenceBundle with an arbitrary object must stop at the RAG boundary."""
    async def route(_request: OrchestrationRequest) -> RouteDecision:
        return RouteDecision(
            intent="knowledge_retrieval",
            confidence=0.9,
            requires_plan=False,
            allowed_capabilities=frozenset({"rag"}),
            reason="Direct lookup.",
        )

    async def plan(_request: OrchestrationRequest, _route: RouteDecision) -> TaskPlan:
        raise AssertionError("simple requests must not plan")

    async def invalid_retriever(
        _request: OrchestrationRequest,
        _route: RouteDecision,
        _plan: TaskPlan | None,
    ) -> EvidenceBundle:
        return object()  # type: ignore[return-value]

    async def tools(
        _request: OrchestrationRequest,
        _route: RouteDecision,
        _plan: TaskPlan,
        _evidence: EvidenceBundle,
    ) -> tuple[ToolResult, ...]:
        raise AssertionError("simple requests must not invoke tools")

    async def synthesize(
        _request: OrchestrationRequest,
        route_decision: RouteDecision,
        _plan: TaskPlan | None,
        _evidence: EvidenceBundle,
        _tool_results: tuple[ToolResult, ...],
    ) -> FinalAnswer:
        raise AssertionError("invalid evidence must never reach synthesis")

    engine = OrchestrationEngine(
        services=OrchestrationServices(
            router=route,
            planner=plan,
            retriever=invalid_retriever,
            tool_runner=tools,
            synthesizer=synthesize,
        )
    )

    with pytest.raises(StageExecutionError, match="stage 'rag' failed"):
        await engine.execute(OrchestrationRequest(question="What is RAG?"))
