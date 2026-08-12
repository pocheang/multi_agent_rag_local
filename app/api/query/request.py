"""Request/response handlers for the QueryMind API compatibility route."""

import logging
from typing import Any

from fastapi import Depends, Request

from app.api.dependencies import (
    _audit,
    _history_store_for_user,
    _is_overload_mode,
    _promote_long_term_memory,
    _query_cache_key,
    _require_existing_session_for_query,
    _require_permission,
    _require_user,
    _trace_id,
    query_result_cache,
    quota_guard,
    runtime_metrics,
)
from app.api.query.execution import execute_standard_query, prepare_standard_query
from app.api.query.response import (
    ensure_trackable_execution_result,
    parse_query_response,
    prepare_query_response,
)
from app.api.schemas import QueryRequest
from app.api.transport.errors import bad_request, conflict, rate_limited
from app.services.input_normalizer import normalize_and_validate_user_question
from app.services.observability.alerting import emit_alert
from app.services.security.quota import QuotaExceededError

logger = logging.getLogger(__name__)


def overload_mode_enabled() -> bool:
    """Small helper for routes that need to degrade gracefully under load."""
    return _is_overload_mode()


def query(req: QueryRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "query:run", request, "query")
    req.session_id = _require_existing_session_for_query(user, req.session_id)
    try:
        quota_guard.enforce_query_quota(user)
    except QuotaExceededError as e:
        runtime_metrics.inc("query_quota_exceeded_total")
        emit_alert(
            "query_quota_exceeded",
            {"trace_id": _trace_id(request), "message": str(e), "user_id": str(user.get("user_id", ""))},
        )
        raise rate_limited(str(e))
    try:
        normalized_question = normalize_and_validate_user_question(req.question)
    except ValueError as e:
        raise bad_request(str(e))
    plan = prepare_standard_query(
        user=user,
        session_id=req.session_id,
        question=normalized_question,
        force_language=req.force_language,
        request_id=req.request_id,
        agent_class_hint=req.agent_class_hint,
        retrieval_strategy=req.retrieval_strategy,
        use_web_fallback=req.use_web_fallback,
        use_reasoning=req.use_reasoning,
    )
    prepared_request = plan.preparation
    original_question = prepared_request.original_question
    effective_question = prepared_request.effective_question
    retrieval_strategy = prepared_request.retrieval_strategy
    strategy_meta = prepared_request.strategy_meta
    is_fast_smalltalk = prepared_request.is_fast_smalltalk
    effective_use_reasoning = prepared_request.effective_use_reasoning
    if prepared_request.early_response is not None:
        pipeline_result = plan.pipeline.execute_prepared_standard_sync(prepared_request)
        payload = {
            "answer": pipeline_result.answer,
            "route": pipeline_result.route.route,
            "skill": pipeline_result.route.skill,
            "agent_class": pipeline_result.route.agent_class,
        }
        early = prepared_request.early_response
        if req.session_id:
            history_store = _history_store_for_user(user)
            history_store.append_message(req.session_id, "user", original_question)
            history_store.append_message(
                req.session_id,
                "assistant",
                str(payload.get("answer", early.answer)),
                metadata={
                    "route": str(payload.get("route", early.route)),
                    "agent_class": str(payload.get("agent_class", early.agent_class)),
                    "web_used": False,
                    "graph_entities": [],
                    "citations": [],
                },
            )
        _audit(
            request,
            action="query.run",
            resource_type="query",
            result="success",
            user=user,
            resource_id=req.session_id or None,
            detail=early.reason,
        )
        return prepare_query_response(
            result={
                "answer": str(payload.get("answer", early.answer)),
                "route": str(payload.get("route", early.route)),
                "skill": str(payload.get("skill", early.skill)),
                "agent_class": str(payload.get("agent_class", early.agent_class)),
            },
            consistency_info={"checked": False},
            request_trace_id=_trace_id(request),
            user=user,
            session_id=req.session_id,
            effective_question=effective_question,
            requested_use_reasoning=req.use_reasoning,
            effective_use_reasoning=effective_use_reasoning,
            is_fast_smalltalk=is_fast_smalltalk,
            retrieval_strategy=retrieval_strategy,
            strategy_meta=strategy_meta,
        ).response
    try:
        if prepared_request.request.use_web_fallback:
            quota_guard.enforce_web_quota(user)
    except QuotaExceededError as e:
        runtime_metrics.inc("query_quota_exceeded_total")
        emit_alert(
            "query_quota_exceeded",
            {"trace_id": _trace_id(request), "message": str(e), "user_id": str(user.get("user_id", ""))},
        )
        raise rate_limited(str(e))
    cache_key = _query_cache_key(
        user=user,
        session_id=req.session_id,
        question=effective_question,
        use_web_fallback=prepared_request.request.use_web_fallback,
        use_reasoning=effective_use_reasoning,
        retrieval_strategy=prepared_request.request.retrieval_strategy,
        agent_class_hint=prepared_request.request.source_scope.agent_class_hint,
        request_id=req.request_id,
        mode="query",
    )
    cached_response = (
        None
        if is_fast_smalltalk
        else query_result_cache.get(cache_key, session_id=req.session_id, user_id=str(user.get("user_id", "")))
    )
    if isinstance(cached_response, dict) and cached_response:
        try:
            cached_payload = ensure_trackable_execution_result(cached_response, question=original_question, user=user)
            cached = parse_query_response(cached_payload)
        except (ValueError, TypeError) as e:
            logger.warning(f"Invalid cached query response: {e}")
            runtime_metrics.inc("query_cache_invalid_total")
            emit_alert(
                "query_cache_invalid_payload",
                {
                    "trace_id": _trace_id(request),
                    "session_id": str(req.session_id or ""),
                },
            )
        else:
            runtime_metrics.inc("query_cache_hit_total")
            return cached
    if not query_result_cache.mark_inflight(cache_key):
        runtime_metrics.inc("query_duplicate_total")
        hot_cached = (
            None
            if is_fast_smalltalk
            else query_result_cache.get(cache_key, session_id=req.session_id, user_id=str(user.get("user_id", "")))
        )
        if isinstance(hot_cached, dict) and hot_cached:
            try:
                hot_cached_payload = ensure_trackable_execution_result(
                    hot_cached, question=original_question, user=user
                )
                return parse_query_response(hot_cached_payload)
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid hot cached query response: {e}")
                runtime_metrics.inc("query_cache_invalid_total")
        emit_alert(
            "query_duplicate_inflight",
            {"trace_id": _trace_id(request), "session_id": str(req.session_id or "")},
        )
        raise conflict("duplicate request in progress")

    result, consistency_info = execute_standard_query(
        request=request,
        user=user,
        session_id=req.session_id,
        plan=plan,
        cache_key=cache_key,
        overload_mode_enabled=overload_mode_enabled,
    )

    prepared = prepare_query_response(
        result=result,
        consistency_info=consistency_info,
        request_trace_id=_trace_id(request),
        user=user,
        session_id=req.session_id,
        effective_question=effective_question,
        requested_use_reasoning=req.use_reasoning,
        effective_use_reasoning=effective_use_reasoning,
        is_fast_smalltalk=is_fast_smalltalk,
        retrieval_strategy=retrieval_strategy,
        strategy_meta=strategy_meta,
    )
    if req.session_id:
        history_store = _history_store_for_user(user)
        history_store.append_message(req.session_id, "user", original_question)
        history_store.append_message(
            req.session_id,
            "assistant",
            result.get("answer", ""),
            metadata=prepared.history_metadata,
        )
        _promote_long_term_memory(user=user, session_id=req.session_id, question=original_question, result=result)
    _audit(
        request,
        action="query.run",
        resource_type="query",
        result="success",
        user=user,
        resource_id=req.session_id or None,
        detail=f"grounding_support={prepared.grounding_support:.3f}",
    )
    query_result_cache.set(
        cache_key,
        prepared.response.model_dump(),
        session_id=req.session_id,
        user_id=str(user.get("user_id", "")),
    )
    runtime_metrics.inc("query_success_total")
    return prepared.response
