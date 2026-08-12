"""
API routes for advanced RAG functionality.
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.dependencies import _require_permission, _require_user
from app.api.deps.documents import _allowed_sources_for_user
from app.api.transport.errors import internal_error
from app.domain.advanced_rag import AdvancedRAGResult
from app.pipeline.contracts import PipelineRequest, PipelineUser, SourceScope
from app.pipeline.profiles import PipelineProfile
from app.pipeline.rag_pipeline import RAGPipeline
from app.services.observability.agent_execution_tracker import AgentExecutionTracker

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/advanced-rag", tags=["advanced-rag"])


class AdvancedRAGRequest(BaseModel):
    """Request model for advanced RAG query."""

    query: str = Field(..., description="User query")
    enable_decomposition: bool = Field(
        default=False,
        description="Enable query decomposition",
    )
    enable_self_rag: bool = Field(
        default=False,
        description="Enable Self-RAG evaluation",
    )
    allowed_sources: list[str] | None = Field(
        default=None,
        description="Optional list of allowed sources",
    )
    retrieval_strategy: str | None = Field(
        default=None,
        description="Optional retrieval strategy",
    )


def _resolve_advanced_allowed_sources(
    user: dict[str, Any],
    requested_sources: list[str] | None,
) -> list[str]:
    visible_sources = _allowed_sources_for_user(user)
    if requested_sources is None:
        return visible_sources

    requested = {str(source or "").strip() for source in requested_sources if str(source or "").strip()}
    if not requested:
        return []
    return [source for source in visible_sources if source in requested]


@router.post("/query", response_model=AdvancedRAGResult)
async def process_advanced_rag_query(
    request_data: AdvancedRAGRequest,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    """
    Process query with advanced RAG techniques.

    This endpoint supports:
    - Query decomposition: Break complex queries into simpler sub-queries
    - Self-RAG: Evaluate retrieval relevance and answer quality

    Args:
        request_data: AdvancedRAGRequest with query and configuration

    Returns:
        AdvancedRAGResult with complete processing results
    """
    _require_permission(user, "query:run", request, "advanced-rag")
    tracker = AgentExecutionTracker.get_instance()
    execution_id = tracker.start_execution(
        request_data.query,
        user_id=str(user.get("user_id", "") or "") or None,
        profile="advanced",
    )
    try:
        allowed_sources = _resolve_advanced_allowed_sources(user, request_data.allowed_sources)
        pipeline_request = PipelineRequest(
            question=request_data.query,
            profile=PipelineProfile.ADVANCED,
            user=PipelineUser(
                user_id=str(user.get("user_id", "") or "") or None,
                username=str(user.get("username", "") or "") or None,
                role=str(user.get("role", "") or "") or None,
                permissions=frozenset(user.get("permissions") or []),
            ),
            source_scope=SourceScope(allowed_sources=frozenset(allowed_sources)),
            retrieval_strategy=request_data.retrieval_strategy,
            enable_decomposition=request_data.enable_decomposition,
            enable_self_rag=request_data.enable_self_rag,
        )
        pipeline_result = await RAGPipeline().execute(pipeline_request)
        result = AdvancedRAGResult(
            query=request_data.query,
            decomposed_query=None,
            sub_query_results=[],
            final_answer=pipeline_result.answer,
            answer_quality=None,
            metadata={
                "route": pipeline_result.route.route,
                "citations": [citation.model_dump(mode="json") for citation in pipeline_result.citations],
                "validation": pipeline_result.execution_metadata.get("validation", {}),
            },
        )
        tracker.complete_execution(execution_id, result.model_dump())
        return result
    except Exception as e:
        tracker.fail_execution(execution_id, str(e))
        logger.error(f"Error processing advanced RAG query: {e}", exc_info=True)
        raise internal_error(f"Error processing query: {str(e)}")


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "advanced-rag",
        "features": {
            "query_decomposition": True,
            "self_rag": True,
        },
    }


@router.get("/config")
async def get_config():
    """Get current advanced RAG configuration."""
    import os

    return {
        "query_decomposition": {
            "enabled_by_default": os.getenv("ENABLE_QUERY_DECOMPOSITION", "false").lower() == "true",
            "max_sub_queries": int(os.getenv("QUERY_DECOMPOSITION_MAX_SUBQUERIES", "4")),
        },
        "self_rag": {
            "enabled_by_default": os.getenv("ENABLE_SELF_RAG", "false").lower() == "true",
            "relevance_threshold": float(os.getenv("SELF_RAG_RELEVANCE_THRESHOLD", "0.6")),
            "quality_threshold": float(os.getenv("SELF_RAG_QUALITY_THRESHOLD", "0.7")),
        },
    }

