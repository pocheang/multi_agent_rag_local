"""Standard RAG Pipeline Internal Contract

⚠️ INTERNAL API - Not for external use

This module provides the canonical RAG pipeline execution interface used
internally by multiple services. Despite being in the 'compatibility' directory,
this is NOT deprecated code - it's an active internal API.

Purpose:
    Standardized RAG pipeline execution with consistent parameters and return
    contract across different internal entry points.

Used by:
    - app/api/routes/admin/ops.py: Performance profiling and benchmarking
    - app/api/routes/public/sessions.py: Message rerun functionality

The execute_standard_compatibility() function encapsulates the full RAG pipeline
with standardized parameters, making it easier to maintain consistency across
different services without duplicating complex setup logic.
"""

from __future__ import annotations

from app.pipeline.contracts import ConversationMessage, PipelineRequest, PipelineUser, SourceScope
from app.pipeline.profiles import PipelineProfile
from app.pipeline.rag_pipeline import RAGPipeline


def execute_standard_compatibility(
    *,
    question: str,
    use_web_fallback: bool = False,
    use_reasoning: bool = False,
    memory_context: str = "",
    allowed_sources: list[str] | None = None,
    user: PipelineUser | None = None,
    session_id: str | None = None,
) -> dict[str, object]:
    """Execute the standard RAG pipeline profile with unified parameters.

    This function provides a standardized interface for RAG pipeline execution,
    used internally by admin operations and session management.

    Args:
        question: User's question to answer
        use_web_fallback: Enable web search fallback if local results insufficient
        use_reasoning: Enable reasoning mode for complex queries
        memory_context: Conversation context/history as string
        allowed_sources: List of allowed document sources (for filtering)
        user: User information for permissions and tracking
        session_id: Session identifier for tracking and history

    Returns:
        Dictionary containing answer, citations, and metadata in standard format
    """
    conversation = (ConversationMessage(role="system", content=memory_context),) if memory_context else ()
    pipeline_result = RAGPipeline().execute_sync(
        PipelineRequest(
            question=question,
            profile=PipelineProfile.ADVANCED,
            session_id=session_id,
            conversation=conversation,
            user=user,
            source_scope=SourceScope(
                allowed_sources=frozenset(allowed_sources) if allowed_sources is not None else None
            ),
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
