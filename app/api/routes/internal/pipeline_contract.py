"""Standard RAG Pipeline Internal Contract

⚠️ INTERNAL API - Not for external use

This module provides the canonical RAG pipeline execution interface used
internally by multiple services.

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

from typing import Any

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
    summary = retrieval_summary(dict(pipeline_result.execution_metadata))
    graph_entities = sorted(
        {
            context.source
            for context in pipeline_result.contexts
            if str(getattr(context, "retriever", "")) == "graph" and context.source
        }
    )
    return {
        "answer": pipeline_result.answer,
        "route": pipeline_result.route.route,
        "reason": pipeline_result.route.reason,
        "citations": citations,
        "vector_result": {"citations": citations},
        # Derived from the run's own diagnostics. `sessions.py` read these two
        # keys off a shape this function never produced, so the rerun path
        # recorded `web_used=False` and no graph entities on every message.
        "web_result": {"used": summary["web_used"], "citations": []},
        "graph_result": {"entities": graph_entities},
        "retrieval": summary,
        "grounding": pipeline_result.execution_metadata.get("grounding", {}),
        "answer_safety": pipeline_result.execution_metadata.get("safety", {}),
        "validation": pipeline_result.execution_metadata.get("validation", {}),
        "execution_metadata": dict(pipeline_result.execution_metadata),
    }


def retrieval_summary(execution_metadata: dict[str, Any]) -> dict[str, Any]:
    """What the client can honestly say about where the answer came from.

    Both entry points used to claim `web_used=False` on every answer. The chat
    endpoint never set the field at all, so the badge read `web: no` however
    much the web had contributed; the rerun endpoint read it off a
    `web_result` key that `execute_standard_compatibility` does not return. The
    same went for `graph_entities`, and `score_memory_candidate` weights
    `web_used` at 0.20, so every memory candidate has been scoring as though the
    answer were purely local.

    `used` means the source *contributed evidence*, not that it was selected: a
    web search that returned nothing is not what a reader means by "this answer
    used the web". `sources` keeps the fuller picture -- including a source that
    ran and found nothing, and one skipped because the caller has no documents.
    """
    diagnostics = execution_metadata.get("workflow_diagnostics") or {}
    knowledge = diagnostics.get("knowledge_diagnostics") or {}
    status = dict(knowledge.get("source_status") or {})
    counts = dict(knowledge.get("source_result_count") or {})
    errors = dict(knowledge.get("source_error_type") or {})

    sources = [
        {
            "source": str(name),
            "status": str(state),
            "count": int(counts.get(name, 0) or 0),
            "reason": str(errors[name]) if name in errors else None,
        }
        for name, state in status.items()
    ]
    contributed = {item["source"] for item in sources if item["status"] == "completed" and item["count"] > 0}
    return {
        "web_used": "web" in contributed,
        "sources": sources,
        "contributing_sources": sorted(contributed),
    }


__all__ = ["execute_standard_compatibility", "retrieval_summary"]
