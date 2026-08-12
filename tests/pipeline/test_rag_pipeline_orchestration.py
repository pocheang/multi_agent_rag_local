"""Regression coverage for the RAGPipeline-to-engine migration seam."""

import pytest

from app.domain.contracts import EvidenceBundle, FinalAnswer, RouteDecision, TaskPlan, ToolResult
from app.orchestration.request import OrchestrationRequest
from app.pipeline.capabilities import CoreCapabilities
from app.pipeline.contracts import PipelineRequest
from app.pipeline.profiles import PipelineProfile
from app.pipeline.rag_pipeline import RAGPipeline


class RecordingEngine:
    def __init__(self) -> None:
        self.requests: list[OrchestrationRequest] = []

    async def execute(self, request: OrchestrationRequest) -> FinalAnswer:
        self.requests.append(request)
        return FinalAnswer(
            text="Typed answer",
            citations=(),
            route=RouteDecision(
                intent="knowledge_retrieval",
                confidence=0.9,
                requires_plan=False,
                allowed_capabilities=frozenset({"rag"}),
                reason="Direct lookup.",
            ),
        )


@pytest.mark.asyncio
async def test_pipeline_delegates_typed_request_to_orchestration_engine() -> None:
    """Bypassing the engine would make the injected engine record no request."""
    engine = RecordingEngine()
    pipeline = RAGPipeline(engine=engine)

    result = await pipeline.execute(PipelineRequest(question="What is RAG?", profile=PipelineProfile.STANDARD))

    assert result.answer == "Typed answer"
    assert result.route.route == "knowledge_retrieval"
    assert engine.requests == [OrchestrationRequest(question="What is RAG?", profile="standard")]


class _TypedRouter:
    async def route(self, request: OrchestrationRequest) -> RouteDecision:
        return RouteDecision(
            intent="knowledge_retrieval",
            confidence=0.8,
            requires_plan=False,
            allowed_capabilities=frozenset({"rag"}),
            reason=f"typed route for {request.question}",
        )


class _TypedPlanner:
    async def plan(self, request: OrchestrationRequest, route: RouteDecision) -> TaskPlan:
        raise AssertionError("a direct retrieval route must not be planned")


class _TypedRAG:
    def set_degradation_reporter(self, reporter: object) -> None:
        self.reporter = reporter

    async def retrieve(
        self,
        request: OrchestrationRequest,
        route: RouteDecision,
        plan: TaskPlan | None,
    ) -> EvidenceBundle:
        assert request.question == "What is typed orchestration?"
        assert route.intent == "knowledge_retrieval"
        assert plan is None
        return EvidenceBundle()


class _TypedTools:
    async def run(
        self,
        request: OrchestrationRequest,
        route: RouteDecision,
        plan: TaskPlan,
        evidence: EvidenceBundle,
    ) -> tuple[ToolResult, ...]:
        raise AssertionError("a direct retrieval route must not invoke tools")


class _TypedSynthesizer:
    async def synthesize(
        self,
        request: OrchestrationRequest,
        route: RouteDecision,
        plan: TaskPlan | None,
        evidence: EvidenceBundle,
        tool_results: tuple[ToolResult, ...],
    ) -> FinalAnswer:
        assert request.question == "What is typed orchestration?"
        assert plan is None
        assert evidence == EvidenceBundle()
        assert tool_results == ()
        return FinalAnswer(text="Typed default answer", citations=("typed-doc:3",), route=route)


@pytest.mark.asyncio
async def test_default_pipeline_executes_typed_engine_instead_of_compatibility_adapter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Passing the compatibility adapter to the default engine would raise this sentinel error."""

    async def unexpected_compatibility(self: RAGPipeline, request: OrchestrationRequest) -> object:
        del self, request
        raise AssertionError("default execution must not enter the legacy compatibility adapter")

    monkeypatch.setattr(RAGPipeline, "_execute_compatibility", unexpected_compatibility)
    pipeline = RAGPipeline(
        capabilities=CoreCapabilities(
            typed_router=_TypedRouter(),
            typed_planner=_TypedPlanner(),
            typed_rag=_TypedRAG(),
            typed_tools=_TypedTools(),
            typed_synthesizer=_TypedSynthesizer(),
        )
    )

    result = await pipeline.execute(
        PipelineRequest(question="What is typed orchestration?", profile=PipelineProfile.STANDARD)
    )

    assert result.answer == "Typed default answer"
    assert result.citations[0].source == "typed-doc:3"
    assert result.route.route == "knowledge_retrieval"
