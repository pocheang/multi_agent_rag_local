"""Synchronous adapters from legacy route payloads to the unified pipeline."""

from __future__ import annotations

from app.pipeline.contracts import ConversationMessage, PipelineRequest, PipelineUser, SourceScope
from app.pipeline.profiles import PipelineProfile
from app.pipeline.rag_pipeline import RAGPipeline


def execute_standard_compatibility(
    *,
    question: str,
    retrieval_strategy: str | None = None,
    use_web_fallback: bool = False,
    use_reasoning: bool = False,
    memory_context: str = "",
    allowed_sources: list[str] | None = None,
    user: PipelineUser | None = None,
    session_id: str | None = None,
) -> dict[str, object]:
    """Execute the standard profile and expose a typed compatibility shape."""
    conversation = (ConversationMessage(role="system", content=memory_context),) if memory_context else ()
    pipeline_result = RAGPipeline().execute_sync(
        PipelineRequest(
            question=question,
            profile=PipelineProfile.STANDARD,
            session_id=session_id,
            conversation=conversation,
            user=user,
            source_scope=SourceScope(allowed_sources=frozenset(allowed_sources) if allowed_sources is not None else None),
            retrieval_strategy=retrieval_strategy,
            use_web_fallback=use_web_fallback,
            use_reasoning=use_reasoning,
        )
    )
    citations = [citation.model_dump(mode="json") for citation in pipeline_result.citations]
    return {
        "answer": pipeline_result.answer,
        "route": pipeline_result.route.route,
        "reason": pipeline_result.route.reason,
        "citations": citations,
        "vector_result": {"citations": citations},
        "grounding": pipeline_result.execution_metadata.get("grounding", {}),
        "answer_safety": pipeline_result.execution_metadata.get("safety", {}),
        "validation": pipeline_result.execution_metadata.get("validation", {}),
        "execution_metadata": dict(pipeline_result.execution_metadata),
    }


__all__ = ["execute_standard_compatibility"]

