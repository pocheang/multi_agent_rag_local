"""Regression coverage for the pipeline-owned standard streaming compatibility adapter."""

from collections.abc import Iterator

import pytest

from app.pipeline.contracts import PipelineRequest, PipelineUser, SourceScope
from app.pipeline.profiles import PipelineProfile
from app.pipeline.rag_pipeline import RAGPipeline


@pytest.mark.asyncio
async def test_pipeline_owns_standard_stream_execution_and_preserves_legacy_events() -> None:
    """A route that invokes the legacy stream directly would bypass this pipeline boundary."""
    calls: list[tuple[str, dict[str, object]]] = []

    def legacy_stream(question: str, **kwargs: object) -> Iterator[dict[str, object]]:
        calls.append((question, kwargs))
        yield {"type": "status", "message": "routing"}
        yield {"type": "answer_chunk", "content": "answer"}
        yield {"type": "done", "result": {"answer": "answer", "execution_id": kwargs["execution_id"]}}

    pipeline = RAGPipeline(standard_stream_executor=legacy_stream)
    request = PipelineRequest(
        question="What is RAG?",
        profile=PipelineProfile.STANDARD,
        session_id="session-1",
        user=PipelineUser(user_id="user-1"),
        source_scope=SourceScope(allowed_sources=frozenset({"doc-a"})),
        use_reasoning=True,
    )

    events = [event async for event in pipeline.execute_stream(request, execution_id="execution-1")]

    assert events == [
        {"type": "status", "message": "routing"},
        {"type": "answer_chunk", "content": "answer"},
        {"type": "done", "result": {"answer": "answer", "execution_id": "execution-1"}},
    ]
    assert calls == [
        (
            "What is RAG?",
            {
                "use_web_fallback": False,
                "use_reasoning": True,
                "memory_context": "",
                "allowed_sources": ["doc-a"],
                "agent_class_hint": None,
                "retrieval_strategy": None,
                "force_language": "",
                "session_id": "session-1",
                "user_id": "user-1",
                "enable_tracking": True,
                "execution_id": "execution-1",
            },
        )
    ]
