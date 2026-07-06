"""Query routes for the QueryMind API."""

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Form, Request

from app.api.dependencies import (
    _audit,
    _build_memory_context_for_session,
    _build_user_file_inventory_answer,
    _call_with_supported_kwargs,
    _effective_strategy_for_session,
    _enforce_result_source_scope,
    _history_store_for_user,
    _is_file_inventory_question,
    _is_overload_mode,
    _latest_answer_for_same_question,
    _launch_shadow_run,
    _normalize_agent_class_hint,
    _promote_long_term_memory,
    _query_cache_key,
    _query_limiter_key,
    _require_existing_session_for_query,
    _require_permission,
    _require_user,
    _resolve_effective_agent_class,
    _resynthesize_after_source_scope,
    _run_with_query_runtime,
    _sse_response,
    _trace_id,
    _user_api_settings_for_runtime,
    query_guard,
    query_result_cache,
    quota_guard,
    runtime_metrics,
    settings,
)
from app.api.utils.document_helpers import _allowed_sources_for_user
from app.api.utils.error_responses import bad_request, conflict, rate_limited
from app.core.schemas import Citation, QueryRequest, QueryResponse
from app.graph.streaming import encode_sse, run_query_stream
from app.graph.workflow import run_query
from app.services.agent_execution_tracker import AgentExecutionTracker
from app.services.alerting import emit_alert, resolve_signing_secret, sign_payload
from app.services.consistency_guard import should_stabilize, text_similarity
from app.services.evidence_conflict import detect_evidence_conflict
from app.services.input_normalizer import (
    enhance_user_question_for_completion,
    normalize_and_validate_user_question,
)
from app.services.network_security import OutboundURLValidationError
from app.services.query_guard import QueryOverloadedError, QueryRateLimitedError
from app.services.query_intent import is_casual_chat_query
from app.services.quota_guard import QuotaExceededError
from app.services.rag_runtime_scope import execution_route_from_result
from app.services.request_context import request_context
from app.services.retrieval_profiles import profile_force_local_only, profile_to_strategy
from app.services.runtime_ops import feature_enabled

router = APIRouter(prefix="/query", tags=["query"])
logger = logging.getLogger(__name__)


def overload_mode_enabled() -> bool:
    """Small helper for routes that need to degrade gracefully under load."""
    return _is_overload_mode()



def _ensure_trackable_execution_result(
    result: dict[str, Any],
    *,
    question: str,
    user: dict[str, Any],
) -> dict[str, Any]:
    """Ensure cached responses still point to a live execution trace."""
    payload = dict(result or {})
    tracker = AgentExecutionTracker.get_instance()
    execution_id = str(payload.get("execution_id", "") or "").strip()
    if execution_id and tracker.get_execution_trace(execution_id) is not None:
        return payload

    execution_id = tracker.start_execution(
        question,
        user_id=str(user.get("user_id", "") or "") or None,
    )
    payload["execution_id"] = execution_id
    tracker.complete_execution(execution_id, payload)
    return payload
def _maybe_sign_response(
    payload: dict[str, Any],
    *,
    user: dict[str, Any],
    session_id: str,
    question: str,
) -> tuple[str | None, str | None]:
    """Attach an optional HMAC signature to response metadata."""
    if not bool(getattr(settings, "response_signing_enabled", True)):
        return None, None
    kid, secret = resolve_signing_secret()
    if not kid or not secret:
        return None, None
    signed_payload = {
        "payload": payload,
        "user_id": str(user.get("user_id", "") or ""),
        "session_id": str(session_id or ""),
        "question": str(question or ""),
    }
    return sign_payload(signed_payload, secret), kid


@router.post("", response_model=QueryResponse)
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
    original_question = normalized_question
    effective_agent_class = _resolve_effective_agent_class(normalized_question, req.agent_class_hint)
    pdf_allowed_sources: list[str] | None = None

    if _is_file_inventory_question(normalized_question):
        answer = _build_user_file_inventory_answer(user)
        if req.session_id:
            history_store = _history_store_for_user(user)
            history_store.append_message(req.session_id, "user", original_question)
            history_store.append_message(
                req.session_id,
                "assistant",
                answer,
                metadata={
                    "route": "policy",
                    "agent_class": "policy",
                    "web_used": False,
                    "graph_entities": [],
                    "citations": [],
                },
            )
        return QueryResponse(
            answer=answer,
            route="policy",
            citations=[],
            graph_entities=[],
            web_used=False,
            debug={"reason": "user_file_inventory_only"},
        )

    if effective_agent_class == "pdf_text":
        from app.api.utils.query_helpers import handle_pdf_agent_routing

        modified_question, pdf_allowed_sources, early_response = handle_pdf_agent_routing(
            normalized_question, user, req.session_id, request, action_name="query.run"
        )

        if early_response is not None:
            return QueryResponse(
                answer=early_response["answer"],
                route=early_response["route"],
                citations=[],
                graph_entities=[],
                web_used=False,
                debug={
                    "reason": early_response["reason"],
                    "skill": early_response["skill"],
                    "agent_class": early_response["agent_class"],
                    "use_reasoning": req.use_reasoning,
                },
            )

        if modified_question:
            normalized_question = modified_question

    is_fast_smalltalk = is_casual_chat_query(normalized_question)
    effective_question = (
        normalized_question if is_fast_smalltalk else enhance_user_question_for_completion(normalized_question)
    )
    memory_context = (
        ""
        if is_fast_smalltalk
        else _build_memory_context_for_session(
            user=user,
            session_id=req.session_id,
            question=effective_question,
        )
    )
    allowed_sources = pdf_allowed_sources if pdf_allowed_sources is not None else _allowed_sources_for_user(user)
    retrieval_strategy, strategy_meta = _effective_strategy_for_session(
        req_strategy=req.retrieval_strategy,
        user=user,
        session_id=req.session_id,
        question=effective_question,
    )
    effective_use_web_fallback = bool(req.use_web_fallback and (not profile_force_local_only(retrieval_strategy)))
    effective_use_reasoning = bool(req.use_reasoning)
    if is_fast_smalltalk:
        # Fast path for greeting/smalltalk: skip slow reasoning/verification chain.
        effective_use_web_fallback = False
        effective_use_reasoning = False
        retrieval_strategy = "baseline"
        strategy_meta = {"reason": "smalltalk_fast_path", "bucket": "smalltalk"}
    try:
        if effective_use_web_fallback:
            quota_guard.enforce_web_quota(user)
    except QuotaExceededError as e:
        runtime_metrics.inc("query_quota_exceeded_total")
        emit_alert(
            "query_quota_exceeded",
            {"trace_id": _trace_id(request), "message": str(e), "user_id": str(user.get("user_id", ""))},
        )
        raise rate_limited(str(e))
    run_query_kwargs: dict[str, Any] = {
        "use_web_fallback": effective_use_web_fallback,
        "use_reasoning": effective_use_reasoning,
        "memory_context": memory_context,
        "allowed_sources": allowed_sources,
        "force_language": req.force_language,
        "session_id": req.session_id,
        "user_id": str(user.get("user_id", "")),  # 添加 user_id 用于执行追踪
    }
    hinted = _normalize_agent_class_hint(req.agent_class_hint)
    if hinted:
        run_query_kwargs["agent_class_hint"] = hinted
    if retrieval_strategy and (req.retrieval_strategy is not None or retrieval_strategy != "advanced"):
        run_query_kwargs["retrieval_strategy"] = profile_to_strategy(retrieval_strategy)
    cache_key = _query_cache_key(
        user=user,
        session_id=req.session_id,
        question=effective_question,
        use_web_fallback=effective_use_web_fallback,
        use_reasoning=effective_use_reasoning,
        retrieval_strategy=run_query_kwargs.get("retrieval_strategy"),
        agent_class_hint=hinted,
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
            cached_payload = _ensure_trackable_execution_result(cached_response, question=original_question, user=user)
            cached = QueryResponse.model_validate(cached_payload)
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
                hot_cached_payload = _ensure_trackable_execution_result(hot_cached, question=original_question, user=user)
                return QueryResponse.model_validate(hot_cached_payload)
            except (ValueError, TypeError) as e:
                logger.warning(f"Invalid hot cached query response: {e}")
                runtime_metrics.inc("query_cache_invalid_total")
        emit_alert(
            "query_duplicate_inflight",
            {"trace_id": _trace_id(request), "session_id": str(req.session_id or "")},
        )
        raise conflict("duplicate request in progress")

    def _query_pipeline():
        runtime_kwargs = dict(run_query_kwargs)
        if overload_mode_enabled():
            runtime_kwargs["use_web_fallback"] = False
            runtime_kwargs["use_reasoning"] = False
            runtime_kwargs.setdefault("retrieval_strategy", "baseline")
        result_local = _call_with_supported_kwargs(run_query, effective_question, **runtime_kwargs)
        result_local = _enforce_result_source_scope(
            result_local, allowed_sources=allowed_sources, request=request, user=user
        )
        result_local = _resynthesize_after_source_scope(
            result_local,
            question=effective_question,
            memory_context=memory_context,
            use_reasoning=bool(runtime_kwargs.get("use_reasoning", False)),
        )
        consistency_local = {"checked": False}
        if bool(settings.consistency_guard_enabled) and (not is_fast_smalltalk):
            prev_answer = _latest_answer_for_same_question(
                user=user, session_id=req.session_id, question=original_question
            )
            if prev_answer:
                sim = text_similarity(prev_answer, result_local.get("answer", ""))
                consistency_local = {"checked": True, "previous_similarity": round(sim, 4), "stabilized": False}
                if should_stabilize(
                    previous_answer=prev_answer,
                    new_answer=result_local.get("answer", ""),
                    threshold=float(settings.consistency_guard_similarity_threshold),
                ):
                    stabilize_kwargs = dict(runtime_kwargs)
                    stabilize_kwargs["retrieval_strategy"] = "baseline"
                    stabilize_kwargs["use_reasoning"] = False
                    retried = _call_with_supported_kwargs(run_query, effective_question, **stabilize_kwargs)
                    retried = _enforce_result_source_scope(
                        retried, allowed_sources=allowed_sources, request=request, user=user
                    )
                    retried = _resynthesize_after_source_scope(
                        retried,
                        question=effective_question,
                        memory_context=memory_context,
                        use_reasoning=bool(stabilize_kwargs.get("use_reasoning", False)),
                    )
                    retried_sim = text_similarity(prev_answer, retried.get("answer", ""))
                    if retried_sim > sim:
                        result_local = retried
                        consistency_local = {
                            "checked": True,
                            "previous_similarity": round(sim, 4),
                            "retried_similarity": round(retried_sim, 4),
                            "stabilized": True,
                        }
        return result_local, consistency_local

    try:
        result, consistency_info = _run_with_query_runtime(user=user, request=request, fn=_query_pipeline)
    finally:
        query_result_cache.clear_inflight(cache_key)

    # OPTIMIZATION: Extract nested dict access to avoid repeated lookups
    vector_result = result.get("vector_result", {})
    web_result = result.get("web_result", {})
    graph_result = result.get("graph_result", {})

    vector_citations_raw = vector_result.get("citations", [])
    web_citations_raw = web_result.get("citations", [])

    vector_citations = [Citation(**x) for x in vector_citations_raw]
    web_citations = [Citation(**x) for x in web_citations_raw]

    # Note: No need for list() conversion - already lists
    conflict_report = detect_evidence_conflict(vector_citations_raw + web_citations_raw)

    if conflict_report.get("conflict"):
        detected_lang = result.get("detected_language", "zh")
        if detected_lang == "zh":
            warning_msg = "⚠️ 注意：检索到的信息中存在相互矛盾的内容，以下回答已综合考虑多方观点。\n\n"
        else:
            warning_msg = "⚠️ Note: Conflicting information was found in the retrieved sources. The answer below considers multiple perspectives.\n\n"
        result["answer"] = f"{warning_msg}{result.get('answer', '')}"

    execution_route = execution_route_from_result(result)
    if req.session_id:
        history_store = _history_store_for_user(user)
        history_store.append_message(req.session_id, "user", original_question)
        history_store.append_message(
            req.session_id,
            "assistant",
            result.get("answer", ""),
            metadata={
                "route": result.get("route", "unknown"),
                "execution_route": execution_route,
                "agent_class": result.get("agent_class", "general"),
                "web_used": web_result.get("used", False),
                "thoughts": result.get("thoughts", []),
                "graph_entities": graph_result.get("entities", []),
                "citations": vector_citations_raw + web_citations_raw,
                "retrieval_diagnostics": vector_result.get("retrieval_diagnostics", {}),
                "grounding": result.get("grounding", {}),
                "explainability": result.get("explainability", {}),
                "answer_safety": result.get("answer_safety", {}),
                "consistency": consistency_info,
                "evidence_conflict": conflict_report,
                "source_scope": result.get("source_scope", {}),
            },
        )
        _promote_long_term_memory(user=user, session_id=req.session_id, question=original_question, result=result)
    response_payload: dict[str, Any] = {
        "answer": result.get("answer", ""),
        "route": result.get("route", "unknown"),
        "citations": vector_citations + web_citations,
        "graph_entities": graph_result.get("entities", []),
        "web_used": web_result.get("used", False),
        "detected_language": result.get("detected_language", "zh"),
        "execution_id": result.get("execution_id"),  # 添加 execution_id
        "debug": {
            "reason": result.get("reason", ""),
            "skill": result.get("skill", ""),
            "agent_class": result.get("agent_class", "general"),
            "execution_route": execution_route,
            "vector_retrieved": result.get("vector_result", {}).get("retrieved_count", 0),
            "vector_effective_hits": result.get("vector_result", {}).get("effective_hit_count", 0),
            "retrieval_diagnostics": result.get("vector_result", {}).get("retrieval_diagnostics", {}),
            "grounding": result.get("grounding", {}),
            "answer_safety": result.get("answer_safety", {}),
            "explainability": result.get("explainability", {}),
            "consistency": consistency_info,
            "use_reasoning": effective_use_reasoning,
            "requested_use_reasoning": req.use_reasoning,
            "fast_smalltalk_path": is_fast_smalltalk,
            "retrieval_strategy": retrieval_strategy or "advanced",
            "retrieval_strategy_reason": strategy_meta.get("reason"),
            "retrieval_strategy_bucket": strategy_meta.get("bucket"),
            "evidence_conflict": conflict_report,
            "source_scope": result.get("source_scope", {}),
            "trace_id": _trace_id(request),
        },
    }
    signature, signature_kid = _maybe_sign_response(
        {
            "answer": response_payload.get("answer", ""),
            "route": response_payload.get("route", ""),
            "trace_id": response_payload.get("debug", {}).get("trace_id", ""),
        },
        user=user,
        session_id=str(req.session_id or ""),
        question=effective_question,
    )
    if signature:
        response_payload["debug"]["signature"] = signature
        response_payload["debug"]["signature_kid"] = signature_kid
    response = QueryResponse(**response_payload)
    grounding_support = float((result.get("grounding", {}) or {}).get("support_ratio", 0.0) or 0.0)
    _audit(
        request,
        action="query.run",
        resource_type="query",
        result="success",
        user=user,
        resource_id=req.session_id or None,
        detail=f"grounding_support={grounding_support:.3f}",
    )
    _launch_shadow_run(
        user=user,
        session_id=req.session_id,
        question=effective_question,
        primary_result=result,
    )
    query_result_cache.set(
        cache_key, response.model_dump(), session_id=req.session_id, user_id=str(user.get("user_id", ""))
    )
    runtime_metrics.inc("query_success_total")
    return response


@router.post("/query/stream")
@router.post("/stream")
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
):
    _require_permission(user, "query:run", request, "query")
    session_id = _require_existing_session_for_query(user, session_id)
    try:
        quota_guard.enforce_query_quota(user)
    except QuotaExceededError as e:
        runtime_metrics.inc("query_stream_quota_exceeded_total")
        emit_alert(
            "query_stream_quota_exceeded",
            {"trace_id": _trace_id(request), "message": str(e), "user_id": str(user.get("user_id", ""))},
        )
        raise rate_limited(str(e))
    try:
        normalized_question = normalize_and_validate_user_question(question)
    except ValueError as e:
        raise bad_request(str(e))
    original_question = normalized_question
    effective_agent_class = _resolve_effective_agent_class(normalized_question, agent_class_hint)
    pdf_allowed_sources: list[str] | None = None

    if _is_file_inventory_question(normalized_question):
        answer = _build_user_file_inventory_answer(user)
        if session_id:
            history_store = _history_store_for_user(user)
            history_store.append_message(session_id, "user", original_question)
            history_store.append_message(
                session_id,
                "assistant",
                answer,
                metadata={
                    "route": "policy",
                    "agent_class": "policy",
                    "web_used": False,
                    "graph_entities": [],
                    "citations": [],
                },
            )

        def event_gen_file_inventory():
            yield encode_sse({"type": "status", "message": "synthesizing"})
            yield encode_sse({"type": "answer_chunk", "content": answer})
            yield encode_sse(
                {
                    "type": "done",
                    "result": {
                        "answer": answer,
                        "route": "policy",
                        "reason": "user_file_inventory_only",
                        "skill": "policy_guard",
                        "agent_class": "policy",
                        "vector_result": {},
                        "graph_result": {},
                        "web_result": {"used": False, "citations": [], "context": ""},
                        "thoughts": ["仅返回当前用户可访问文件范围内信息。"],
                    },
                }
            )

        return _sse_response(event_gen_file_inventory(), append_terminal_event=True)

    if effective_agent_class == "pdf_text":
        from app.api.utils.query_helpers import handle_pdf_agent_routing

        modified_question, pdf_allowed_sources, early_response = handle_pdf_agent_routing(
            normalized_question, user, session_id, request, action_name="query.stream"
        )

        if early_response is not None:
            answer = early_response["answer"]
            reason = early_response["reason"]

            # Map reason to SSE status message
            status_map = {
                "pdf_agent_no_pdf": "pdf_upload_required",
                "pdf_agent_need_selection": "pdf_selection_required",
                "pdf_agent_chunks_zero": "pdf_reindex_required",
            }
            status_msg = status_map.get(reason, "pdf_routing")

            def event_gen_pdf_early():
                yield encode_sse({"type": "status", "message": status_msg})
                yield encode_sse({"type": "answer_chunk", "content": answer})
                yield encode_sse(
                    {
                        "type": "done",
                        "result": {
                            "answer": answer,
                            "route": "pdf_text",
                            "reason": reason,
                            "skill": "pdf_text_reader",
                            "agent_class": "pdf_text",
                            "vector_result": {},
                            "graph_result": {},
                            "web_result": {"used": False, "citations": [], "context": ""},
                        },
                    }
                )

            return _sse_response(event_gen_pdf_early(), append_terminal_event=True)

        if modified_question:
            normalized_question = modified_question

    is_fast_smalltalk = is_casual_chat_query(normalized_question)
    effective_question = (
        normalized_question if is_fast_smalltalk else enhance_user_question_for_completion(normalized_question)
    )
    history_store = _history_store_for_user(user)
    memory_context = (
        ""
        if is_fast_smalltalk
        else _build_memory_context_for_session(
            user=user,
            session_id=session_id,
            question=effective_question,
        )
    )
    allowed_sources = pdf_allowed_sources if pdf_allowed_sources is not None else _allowed_sources_for_user(user)
    normalized_strategy, strategy_meta = _effective_strategy_for_session(
        req_strategy=retrieval_strategy,
        user=user,
        session_id=session_id,
        question=effective_question,
    )
    effective_use_web_fallback = bool(use_web_fallback and (not profile_force_local_only(normalized_strategy)))
    effective_use_reasoning = bool(use_reasoning)
    logger.info(
        f"[WEB_FALLBACK_DEBUG] use_web_fallback={use_web_fallback}, "
        f"normalized_strategy={normalized_strategy}, "
        f"profile_force_local_only={profile_force_local_only(normalized_strategy)}, "
        f"effective_use_web_fallback={effective_use_web_fallback}"
    )
    if is_fast_smalltalk:
        effective_use_web_fallback = False
        effective_use_reasoning = False
        normalized_strategy = "baseline"
        strategy_meta = {"reason": "smalltalk_fast_path", "bucket": "smalltalk"}
    try:
        if effective_use_web_fallback:
            quota_guard.enforce_web_quota(user)
    except QuotaExceededError as e:
        runtime_metrics.inc("query_stream_quota_exceeded_total")
        emit_alert(
            "query_stream_quota_exceeded",
            {"trace_id": _trace_id(request), "message": str(e), "user_id": str(user.get("user_id", ""))},
        )
        raise rate_limited(str(e))
    hinted = _normalize_agent_class_hint(agent_class_hint)
    stream_retrieval_strategy = (
        profile_to_strategy(normalized_strategy)
        if normalized_strategy and (retrieval_strategy is not None or normalized_strategy != "advanced")
        else None
    )
    stream_cache_key = _query_cache_key(
        user=user,
        session_id=session_id,
        question=effective_question,
        use_web_fallback=effective_use_web_fallback,
        use_reasoning=effective_use_reasoning,
        retrieval_strategy=stream_retrieval_strategy,
        agent_class_hint=hinted,
        request_id=request_id,
        mode="stream",
    )
    replay_enabled = feature_enabled(
        "stream_replay",
        user_id=str(user.get("user_id", "")),
        session_id=str(session_id or ""),
        question=effective_question,
    )
    if replay_enabled and not is_fast_smalltalk:
        stream_replay = query_result_cache.get_stream_events(stream_cache_key)
        replay_events = list(stream_replay.get("events", []) or [])
        replay_done = bool(stream_replay.get("done", False))
        if replay_events:

            async def event_gen_replay():
                for ev in replay_events:
                    if isinstance(ev, dict):
                        yield encode_sse(ev)
                if not replay_done:
                    yield encode_sse({"type": "status", "message": "replay_partial", "trace_id": _trace_id(request)})

            return _sse_response(event_gen_replay(), append_terminal_event=True)

    cached_stream = (
        None
        if is_fast_smalltalk
        else query_result_cache.get(stream_cache_key, session_id=session_id, user_id=str(user.get("user_id", "")))
    )
    if isinstance(cached_stream, dict) and cached_stream.get("result"):
        runtime_metrics.inc("query_stream_cache_hit_total")
        done_result = _ensure_trackable_execution_result(
            dict(cached_stream.get("result", {}) or {}),
            question=original_question,
            user=user,
        )

        async def event_gen_cached():
            yield encode_sse({"type": "status", "message": "cache_hit"})
            answer_text = str(done_result.get("answer", "") or "")
            if answer_text:
                yield encode_sse({"type": "answer_chunk", "content": answer_text})
            yield encode_sse({"type": "done", "result": done_result})

        return _sse_response(event_gen_cached(), append_terminal_event=True)
    if not query_result_cache.mark_inflight(stream_cache_key):
        runtime_metrics.inc("query_stream_duplicate_total")
        emit_alert(
            "query_stream_duplicate_inflight",
            {"trace_id": _trace_id(request), "session_id": str(session_id or "")},
        )
        raise conflict("duplicate request in progress")
    if session_id:
        history_store.append_message(session_id, "user", original_question)
    try:
        runtime_api_settings = _user_api_settings_for_runtime(user)
    except OutboundURLValidationError as e:
        runtime_metrics.inc("query_stream_invalid_api_settings_total")
        emit_alert(
            "query_stream_invalid_api_settings",
            {
                "trace_id": _trace_id(request),
                "user_id": str(user.get("user_id", "")),
                "reason": str(e),
            },
        )
        query_result_cache.clear_inflight(stream_cache_key)
        raise bad_request(f"invalid api settings: {e}")

    async def event_gen():
        final_result = None
        trace_id = _trace_id(request)
        stream_kwargs: dict[str, Any] = {
            "use_web_fallback": effective_use_web_fallback,
            "use_reasoning": effective_use_reasoning,
            "memory_context": memory_context,
            "allowed_sources": allowed_sources,
            "force_language": force_language,
            "session_id": session_id,
            "user_id": str(user.get("user_id", "")),
            "enable_tracking": True,
        }
        if hinted:
            stream_kwargs["agent_class_hint"] = hinted
        if stream_retrieval_strategy:
            stream_kwargs["retrieval_strategy"] = stream_retrieval_strategy
        limiter_key = _query_limiter_key(user, request)
        try:
            with query_guard.acquire(limiter_key):
                with request_context(
                    timeout_ms=int(getattr(settings, "query_request_timeout_ms", 20000) or 20000),
                    overload_mode=_is_overload_mode(),
                    api_settings=runtime_api_settings,
                ):
                    runtime_stream_kwargs = dict(stream_kwargs)
                    if overload_mode_enabled():
                        runtime_stream_kwargs["use_web_fallback"] = False
                        runtime_stream_kwargs["use_reasoning"] = False
                        runtime_stream_kwargs.setdefault("retrieval_strategy", "baseline")
                    hello_event = {"type": "status", "message": "trace", "trace_id": trace_id}
                    if replay_enabled:
                        query_result_cache.append_stream_event(stream_cache_key, hello_event, done=False)
                    yield encode_sse(hello_event)
                    for event in _call_with_supported_kwargs(
                        run_query_stream,
                        effective_question,
                        **runtime_stream_kwargs,
                    ):
                        if event.get("type") == "done":
                            final_result = _enforce_result_source_scope(
                                event.get("result", {}),
                                allowed_sources=allowed_sources,
                                request=request,
                                user=user,
                            )
                            original_stream_answer = str(final_result.get("answer", "") or "")
                            final_result = _resynthesize_after_source_scope(
                                final_result,
                                question=effective_question,
                                memory_context=memory_context,
                                use_reasoning=bool(runtime_stream_kwargs.get("use_reasoning", False)),
                            )
                            if str(final_result.get("answer", "") or "") != original_stream_answer:
                                reset_event = {"type": "answer_reset", "content": final_result.get("answer", "")}
                                if replay_enabled:
                                    query_result_cache.append_stream_event(stream_cache_key, reset_event, done=False)
                                yield encode_sse(reset_event)
                            conflict_report = detect_evidence_conflict(
                                list(final_result.get("vector_result", {}).get("citations", []) or [])
                                + list(final_result.get("web_result", {}).get("citations", []) or [])
                            )
                            final_result["evidence_conflict"] = conflict_report
                            if conflict_report.get("conflict"):
                                final_result["answer"] = (
                                    f"[evidence-conflict-warning]\n{final_result.get('answer', '')}"
                                )
                            final_result["execution_route"] = execution_route_from_result(final_result)
                            final_result["retrieval_strategy"] = normalized_strategy or "advanced"
                            final_result["trace_id"] = trace_id
                            sig, sig_kid = _maybe_sign_response(
                                {
                                    "answer": final_result.get("answer", ""),
                                    "route": final_result.get("route", ""),
                                    "trace_id": trace_id,
                                },
                                user=user,
                                session_id=str(session_id or ""),
                                question=effective_question,
                            )
                            if sig:
                                final_result["signature"] = sig
                                final_result["signature_kid"] = sig_kid
                            event = {**event, "result": final_result}
                            if replay_enabled:
                                query_result_cache.append_stream_event(stream_cache_key, event, done=True)
                                query_result_cache.mark_stream_done(stream_cache_key)
                        else:
                            if replay_enabled:
                                query_result_cache.append_stream_event(stream_cache_key, event, done=False)
                        yield encode_sse(event)
        except QueryRateLimitedError as e:
            runtime_metrics.inc("query_stream_rate_limited_total")
            emit_alert(
                "query_stream_rate_limited",
                {"message": str(e), "trace_id": trace_id},
            )
            yield encode_sse({"type": "error", "error": "rate_limited", "message": str(e)})
            return
        except QueryOverloadedError as e:
            runtime_metrics.inc("query_stream_overloaded_total")
            emit_alert(
                "query_stream_overloaded",
                {"message": str(e), "trace_id": trace_id},
            )
            yield encode_sse({"type": "error", "error": "overloaded", "message": str(e)})
            return
        except Exception as e:
            runtime_metrics.inc("query_stream_internal_error_total")
            logger.exception("query stream unexpected failure")
            emit_alert(
                "query_stream_internal_error",
                {"message": f"{type(e).__name__}: {e}", "trace_id": trace_id},
            )
            yield encode_sse(
                {
                    "type": "error",
                    "error": "internal_error",
                    "message": "query stream failed unexpectedly; please retry.",
                    "trace_id": trace_id,
                }
            )
            return
        finally:
            query_result_cache.clear_inflight(stream_cache_key)

        if session_id and final_result is not None:
            history_store.append_message(
                session_id,
                "assistant",
                final_result.get("answer", ""),
                metadata={
                    "route": final_result.get("route", "unknown"),
                    "execution_route": final_result.get("execution_route", ""),
                    "agent_class": final_result.get("agent_class", "general"),
                    "web_used": final_result.get("web_result", {}).get("used", False),
                    "thoughts": final_result.get("thoughts", []),
                    "graph_entities": final_result.get("graph_result", {}).get("entities", []),
                    "citations": final_result.get("vector_result", {}).get("citations", [])
                    + final_result.get("web_result", {}).get("citations", []),
                    "retrieval_diagnostics": final_result.get("vector_result", {}).get("retrieval_diagnostics", {}),
                    "grounding": final_result.get("grounding", {}),
                    "explainability": final_result.get("explainability", {}),
                    "answer_safety": final_result.get("answer_safety", {}),
                    "retrieval_strategy": normalized_strategy or "advanced",
                    "retrieval_strategy_reason": strategy_meta.get("reason"),
                    "retrieval_strategy_bucket": strategy_meta.get("bucket"),
                    "evidence_conflict": final_result.get("evidence_conflict", {}),
                    "source_scope": final_result.get("source_scope", {}),
                },
            )
            _promote_long_term_memory(user=user, session_id=session_id, question=original_question, result=final_result)
            _launch_shadow_run(
                user=user,
                session_id=session_id,
                question=effective_question,
                primary_result=final_result,
            )
        if final_result is not None:
            query_result_cache.set(
                stream_cache_key, {"result": final_result}, session_id=session_id, user_id=str(user.get("user_id", ""))
            )
            runtime_metrics.inc("query_stream_success_total")

    return _sse_response(event_gen(), append_terminal_event=True)



