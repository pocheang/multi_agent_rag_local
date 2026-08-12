"""Compatibility coverage for all public RAG pipeline profiles."""

import pytest

from app.pipeline.contracts import PipelineRequest
from app.pipeline.profiles import PipelineProfile
from app.pipeline.rag_pipeline import RAGPipeline


class StrictWorkflow:
    def __init__(self, **kwargs: object) -> None:
        self.options = kwargs

    async def execute_query(self, **kwargs: object) -> dict[str, object]:
        assert kwargs["query"] == "How is quality checked?"
        assert kwargs["session_id"] == "session-1"
        return {
            "answer": "With validation.",
            "route_used": "vector",
            "route_reason": "evidence available",
            "quality_report": {},
        }


class AdvancedResult:
    def model_dump(self) -> dict[str, object]:
        return {"answer": "With decomposition.", "route": "hybrid"}


class AdvancedWorkflow:
    def __init__(self, **kwargs: object) -> None:
        self.options = kwargs

    async def process_query(self, **kwargs: object) -> AdvancedResult:
        assert kwargs["query"] == "Compare two systems"
        assert kwargs["retrieval_strategy"] == "advanced"
        return AdvancedResult()


@pytest.mark.asyncio
async def test_strict_quality_profile_preserves_legacy_workflow_shape() -> None:
    """Replacing the strict adapter must not drop its public answer and route fields."""
    result = await RAGPipeline(strict_workflow_factory=StrictWorkflow).execute(
        PipelineRequest(
            question="How is quality checked?",
            profile=PipelineProfile.STRICT_QUALITY,
            session_id="session-1",
        )
    )

    assert result.answer == "With validation."
    assert result.route.route == "vector"


@pytest.mark.asyncio
async def test_advanced_profile_preserves_model_dump_workflow_result() -> None:
    """Advanced workflow model results must remain usable through the compatibility adapter."""
    result = await RAGPipeline(advanced_workflow_factory=AdvancedWorkflow).execute(
        PipelineRequest(
            question="Compare two systems",
            profile=PipelineProfile.ADVANCED,
            retrieval_strategy="advanced",
        )
    )

    assert result.answer == "With decomposition."
    assert result.route.route == "hybrid"


@pytest.mark.asyncio
async def test_pipeline_rejects_profile_override_that_conflicts_with_request() -> None:
    """A caller cannot silently route a standard request through another public profile."""
    with pytest.raises(ValueError, match="must match"):
        await RAGPipeline(standard_executor=lambda *_args, **_kwargs: {}).execute(
            PipelineRequest(question="What is RAG?", profile=PipelineProfile.STANDARD),
            profile=PipelineProfile.ADVANCED,
        )
