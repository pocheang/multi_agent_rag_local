"""Characterization coverage for migration-era RAGPipeline compatibility."""

import pytest

from app.pipeline.contracts import PipelineRequest
from app.pipeline.profiles import PipelineProfile
from app.pipeline.rag_pipeline import RAGPipeline


@pytest.mark.asyncio
async def test_default_engine_keeps_standard_workflow_payload_available() -> None:
    """The compatibility adapter must preserve fields still consumed by public routes."""
    def legacy_executor(question: str, **_kwargs: object) -> dict[str, object]:
        assert question == "What is RAG?"
        return {
            "answer": "Retrieval augmented generation",
            "route": "vector",
            "citations": [{"source": "guide.md", "content": "RAG definition", "document_id": "guide"}],
        }

    result = await RAGPipeline(standard_executor=legacy_executor).execute(
        PipelineRequest(question="What is RAG?", profile=PipelineProfile.STANDARD)
    )

    assert result.answer == "Retrieval augmented generation"
    assert result.route.route == "vector"
    assert result.execution_metadata["compatibility_payload"]["answer"] == "Retrieval augmented generation"
