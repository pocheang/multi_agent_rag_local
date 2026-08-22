"""Canonical HTTP/SSE assembly for versioned public query streams."""

from __future__ import annotations

import logging
from typing import Annotated, Any
from uuid import uuid4

from fastapi import Depends, Form, Request
from fastapi.responses import StreamingResponse

from app.api import dependencies as api_dependencies
from app.api.dependencies import (
    _audit,
    _history_store_for_user,
    _query_cache_key,
    _require_existing_session_for_query,
    _require_permission,
    _require_user,
    _reserve_chat_credit,
    _sse_response,
    _trace_id,
    _user_api_settings_for_runtime,
    runtime_metrics,
)
from app.api.deps.runtime import get_app_services
from app.api.query.response import maybe_sign_response
from app.api.query.streaming.cache import cached_stream_response, claim_stream
from app.api.query.streaming.execution import StreamExecutionContext, stream_execution_events
from app.api.query.streaming.transport import serialize_compatibility_event, versioned_stream_response
from app.api.transport.errors import bad_request, rate_limited
from app.graph.streaming.sse_encoder import encode_sse
from app.pipeline.contracts import PipelineRequest, PipelineUser, SourceScope
from app.pipeline.profiles import PipelineProfile
from app.pipeline.rag_pipeline import RAGPipeline
from app.services.input_normalizer import normalize_and_validate_user_question
from app.services.observability.agent_execution_tracker import AgentExecutionTracker
from app.services.observability.alerting import emit_alert
from app.services.runtime.runtime_ops import feature_enabled
from app.services.security.network import OutboundURLValidationError
from app.services.security.quota import QuotaExceededError

logger = logging.getLogger(__name__)


def _early_stream_response(*, answer: str, status: str, result: dict[str, Any]) -> StreamingResponse:
    """Map an engine-owned early result to the established SSE sequence."""

    async def events():
        yield encode_sse({"type": "status", "message": status})
        yield encode_sse({"type": "answer_chunk", "content": answer})
        yield encode_sse({"type": "done", "result": result})

    return _sse_response(events(), append_terminal_event=True)


async def _stream_query_impl(
    question: Annotated[str, Form(...)],
    request: Request,
    user: dict[str, Any],
    credit_reservation: Any,
    use_web_fallback: Annotated[bool, Form()] = False,
    use_reasoning: Annotated[bool, Form()] = False,
    session_id: Annotated[str | None, Form()] = None,
    request_id: Annotated[str | None, Form()] = None,
    agent_class_hint: Annotated[str | None, Form()] = None,
    retrieval_strategy: Annotated[str | None, Form()] = None,
    force_language: Annotated[str, Form()] = "",
) -> StreamingResponse:
    """Validate transport concerns and delegate all query policy/execution."""
    _require_permission(user, "query:run", request, "query")
    query_runtime = api_dependencies.get_query_runtime()
    query_result_cache = query_runtime.query_result_cache
    quota_guard = query_runtime.quota_guard
    session_id = _require_existing_session_for_query(user, session_id)
    try:
        quota_guard.enforce_query_quota(user)
    except QuotaExceededError as exc:
        runtime_metrics.inc("query_stream_quota_exceeded_total")
        emit_alert(
            "query_stream_quota_exceeded",
            {"trace_id": _trace_id(request), "message": str(exc), "user_id": str(user.get("user_id", ""))},
        )
        raise rate_limited(str(exc))
    try:
        normalized_question = normalize_and_validate_user_question(question)
    except ValueError as exc:
        raise bad_request(str(exc))

    try:
        tool_agent = get_app_services(request.app).tool_agent
    except RuntimeError:
        # The typed pipeline remains usable for minimal ASGI/test hosts that do
        # not install connector services. Connector capabilities are simply
        # unavailable for that request.
        tool_agent = None
    pipeline = RAGPipeline(tool_agent=tool_agent)
    pipeline_request = PipelineRequest(
        question=normalized_question,
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
    prepared = (
        pipeline.prepare_standard_request(pipeline_request) if hasattr(pipeline, "prepare_standard_request") else None
    )
    original_question = prepared.original_question if prepared is not None else normalized_question
    effective_question = prepared.effective_question if prepared is not None else normalized_question
    history_store = _history_store_for_user(user)
    if prepared is not None and prepared.early_response is not None:
        pipeline_result = await pipeline.execute_prepared_standard(prepared)
        result = {
            "answer": pipeline_result.answer,
            "route": pipeline_result.route.route,
            "skill": pipeline_result.route.skill,
            "agent_class": pipeline_result.route.agent_class,
            "citations": [citation.model_dump(mode="json") for citation in pipeline_result.citations],
            "grounding": pipeline_result.execution_metadata.get("grounding", {}),
            "safety": pipeline_result.execution_metadata.get("safety", {}),
            "validation": pipeline_result.execution_metadata.get("validation", {}),
            "execution_metadata": dict(pipeline_result.execution_metadata),
        }
        early = prepared.early_response
        if session_id:
            history_store.append_message(session_id, "user", original_question)
            history_store.append_message(
                session_id,
                "assistant",
                str(result.get("answer", early.answer)),
                metadata={
                    "route": str(result.get("route", early.route)),
                    "agent_class": str(result.get("agent_class", early.agent_class)),
                    "web_used": False,
                    "graph_entities": [],
                    "citations": [],
                },
            )
        status = {
            "user_file_inventory_only": "synthesizing",
            "pdf_agent_no_pdf": "pdf_upload_required",
            "pdf_agent_need_selection": "pdf_selection_required",
            "pdf_agent_chunks_zero": "pdf_reindex_required",
        }.get(early.reason, "pdf_routing")
        credit_reservation.commit()
        return versioned_stream_response(
            _early_stream_response(
                answer=str(result.get("answer", early.answer)),
                status=status,
                result=result,
            )
        )

    try:
        if (prepared.request if prepared is not None else pipeline_request).use_web_fallback:
            quota_guard.enforce_web_quota(user)
    except QuotaExceededError as exc:
        runtime_metrics.inc("query_stream_quota_exceeded_total")
        emit_alert(
            "query_stream_quota_exceeded",
            {"trace_id": _trace_id(request), "message": str(exc), "user_id": str(user.get("user_id", ""))},
        )
        raise rate_limited(str(exc))

    stream_cache_key = _query_cache_key(
        user=user,
        session_id=session_id,
        question=effective_question,
        use_web_fallback=(prepared.request if prepared is not None else pipeline_request).use_web_fallback,
        use_reasoning=prepared.effective_use_reasoning if prepared is not None else use_reasoning,
        retrieval_strategy=(prepared.request if prepared is not None else pipeline_request).retrieval_strategy,
        agent_class_hint=(prepared.request if prepared is not None else pipeline_request).source_scope.agent_class_hint,
        request_id=request_id,
        mode="stream",
        conversation=(prepared.request if prepared is not None else pipeline_request).conversation,
    )
    replay_enabled = feature_enabled(
        "stream_replay",
        user_id=str(user.get("user_id", "")),
        session_id=str(session_id or ""),
        question=effective_question,
    )
    cached_response = cached_stream_response(
        stream_cache_key=stream_cache_key,
        replay_enabled=replay_enabled,
        is_fast_smalltalk=prepared.is_fast_smalltalk if prepared is not None else False,
        request=request,
        user=user,
        session_id=session_id,
        original_question=original_question,
        query_runtime=query_runtime,
    )
    if cached_response is not None:
        credit_reservation.commit()
        return versioned_stream_response(cached_response)
    claim_stream(
        stream_cache_key=stream_cache_key,
        request=request,
        user=user,
        session_id=session_id,
        query_runtime=query_runtime,
    )
    if session_id:
        history_store.append_message(session_id, "user", original_question)
    try:
        runtime_api_settings = _user_api_settings_for_runtime(user)
    except OutboundURLValidationError as exc:
        runtime_metrics.inc("query_stream_invalid_api_settings_total")
        emit_alert(
            "query_stream_invalid_api_settings",
            {"trace_id": _trace_id(request), "user_id": str(user.get("user_id", "")), "reason": str(exc)},
        )
        query_result_cache.clear_inflight(stream_cache_key)
        raise bad_request(f"invalid api settings: {exc}")

    execution_id = str(uuid4())
    AgentExecutionTracker.get_instance().start_execution(
        effective_question,
        execution_id=execution_id,
        user_id=str(user.get("user_id", "") or "") or None,
        profile="standard",
    )
    context = StreamExecutionContext(
        request=request,
        user=user,
        session_id=session_id,
        original_question=original_question,
        effective_question=effective_question,
        normalized_strategy=prepared.retrieval_strategy if prepared is not None else retrieval_strategy,
        strategy_meta=prepared.strategy_meta if prepared is not None else {},
        stream_cache_key=stream_cache_key,
        replay_enabled=replay_enabled,
        runtime_api_settings=runtime_api_settings,
        execution_id=execution_id,
        history_store=history_store,
        pipeline=pipeline,
        pipeline_request=pipeline_request,
        preparation=prepared,
        source_scope_audit=lambda outcome, detail: _audit(
            request,
            action="query.source_scope",
            resource_type="query",
            result=outcome,
            user=user,
            detail=detail,
        ),
        result_signer=lambda result: maybe_sign_response(
            {
                "answer": result.get("answer", ""),
                "route": result.get("route", ""),
                "trace_id": result.get("trace_id", ""),
            },
            user=user,
            session_id=str(session_id or ""),
            question=effective_question,
        ),
        query_runtime=query_runtime,
        credit_reservation=credit_reservation,
    )
    return versioned_stream_response(_sse_response(stream_execution_events(context), append_terminal_event=True))


async def stream_query(
    question: Annotated[str, Form(...)],
    request: Request,
    use_web_fallback: Annotated[bool, Form()] = False,
    use_reasoning: Annotated[bool, Form()] = False,
    session_id: Annotated[str | None, Form()] = None,
    request_id: Annotated[str | None, Form()] = None,
    agent_class_hint: Annotated[str | None, Form()] = None,
    retrieval_strategy: Annotated[str | None, Form()] = None,
    force_language: Annotated[str, Form()] = "",
    user: dict[str, Any] = Depends(_require_user),
) -> StreamingResponse:
    credit_reservation = _reserve_chat_credit(request, user, "query_stream")
    try:
        return await _stream_query_impl(
            question=question,
            request=request,
            use_web_fallback=use_web_fallback,
            use_reasoning=use_reasoning,
            session_id=session_id,
            request_id=request_id,
            agent_class_hint=agent_class_hint,
            retrieval_strategy=retrieval_strategy,
            force_language=force_language,
            user=user,
            credit_reservation=credit_reservation,
        )
    except BaseException:
        credit_reservation.close()
        raise


__all__ = ["serialize_compatibility_event", "stream_query"]
