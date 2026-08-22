"""Normal-query execution behind the public request handler."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from typing import Any

from fastapi import Request

from app.api import dependencies as api_dependencies
from app.api.dependencies import (
    _audit,
    _latest_answer_for_same_question,
    _run_with_query_runtime,
)
from app.pipeline.contracts import PipelineRequest, PipelineUser, SourceScope
from app.pipeline.profiles import PipelineProfile
from app.pipeline.rag_pipeline import RAGPipeline


@dataclass(frozen=True)
class StandardQueryPlan:
    """HTTP request construction plus the pipeline-owned delegation handle."""

    pipeline: RAGPipeline
    preparation: Any


def prepare_standard_query(
    *,
    user: dict[str, Any],
    session_id: str | None,
    question: str,
    force_language: str,
    request_id: str | None,
    agent_class_hint: str | None,
    retrieval_strategy: str | None,
    use_web_fallback: bool,
    use_reasoning: bool,
    standard_executor: Callable[..., Mapping[str, Any]] | None = None,
) -> StandardQueryPlan:
    """Pass the normalized HTTP request to the pipeline's orchestration delegate."""
    del standard_executor
    pipeline = RAGPipeline()
    prepared = pipeline.prepare_standard_request(
        PipelineRequest(
            question=question,
            profile=PipelineProfile.STANDARD,
            session_id=session_id,
            user=PipelineUser(
                user_id=str(user.get("user_id", "") or "") or None,
                username=str(user.get("username", "") or "") or None,
                role=str(user.get("role", "") or "") or None,
                permissions=frozenset(user.get("permissions") or []),
            ),
            source_scope=SourceScope(agent_class_hint=agent_class_hint),
            retrieval_strategy=retrieval_strategy,
            use_web_fallback=use_web_fallback,
            use_reasoning=use_reasoning,
            force_language=force_language,
            request_id=request_id,
        )
    )
    return StandardQueryPlan(pipeline=pipeline, preparation=prepared)


def execute_standard_query(
    *,
    plan: StandardQueryPlan,
    request: Request,
    user: dict[str, Any],
    session_id: str | None,
    cache_key: str,
    overload_mode_enabled: Callable[[], bool],
    query_runtime: api_dependencies.QueryRuntime,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Assemble the HTTP request contract and delegate execution to ``RAGPipeline``."""

    prepared = plan.pipeline.bind_standard_runtime_context(
        plan.preparation,
        user=user,
        overload_mode=overload_mode_enabled(),
        latest_answer=lambda: _latest_answer_for_same_question(
            user=user,
            session_id=session_id,
            question=plan.preparation.original_question,
        ),
        shadow_queue=query_runtime.shadow_queue,
        source_scope_audit=lambda outcome, detail: _audit(
            request,
            action="query.source_scope",
            resource_type="query",
            result=outcome,
            user=user,
            detail=detail,
        ),
    )

    def query_pipeline() -> tuple[dict[str, Any], dict[str, Any]]:
        pipeline_result = plan.pipeline.execute_prepared_standard_sync(prepared)
        payload = {
            "answer": pipeline_result.answer,
            "route": pipeline_result.route.route,
            "reason": pipeline_result.route.reason,
            "citations": [citation.model_dump(mode="json") for citation in pipeline_result.citations],
            "vector_result": {
                "citations": [citation.model_dump(mode="json") for citation in pipeline_result.citations]
            },
            "grounding": pipeline_result.execution_metadata.get("grounding", {}),
            "answer_safety": pipeline_result.execution_metadata.get("safety", {}),
            "validation": pipeline_result.execution_metadata.get("validation", {}),
            "execution_metadata": dict(pipeline_result.execution_metadata),
        }
        return payload, {"checked": False, "owner": "typed_finalization"}

    try:
        return _run_with_query_runtime(
            user=user,
            request=request,
            fn=query_pipeline,
            runtime=query_runtime,
        )
    finally:
        query_runtime.query_result_cache.clear_inflight(cache_key)


__all__ = ["StandardQueryPlan", "execute_standard_query", "prepare_standard_query"]
