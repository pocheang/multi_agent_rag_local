"""Regression coverage for complete pipeline-to-engine request translation."""

import pytest

from app.pipeline.contracts import ConversationMessage, PipelineRequest, PipelineUser, SourceScope
from app.pipeline.profiles import PipelineProfile
from app.pipeline.rag_pipeline import RAGPipeline


@pytest.mark.asyncio
async def test_compatibility_adapter_preserves_conversation_actor_and_scope() -> None:
    """Dropping a public request field at the orchestration boundary is a compatibility bug."""
    def legacy_executor(question: str, **kwargs: object) -> dict[str, object]:
        assert question == "What is RAG?"
        assert kwargs["memory_context"] == "earlier question"
        assert kwargs["allowed_sources"] == ["guide.md"]
        assert kwargs["user_id"] == "user-1"
        return {"answer": "RAG", "route": "vector"}

    request = PipelineRequest(
        question="What is RAG?",
        profile=PipelineProfile.STANDARD,
        conversation=(ConversationMessage(role="system", content="earlier question"),),
        user=PipelineUser(user_id="user-1"),
        source_scope=SourceScope(allowed_sources=frozenset({"guide.md"})),
    )

    result = await RAGPipeline(standard_executor=legacy_executor).execute(request)

    assert result.answer == "RAG"
