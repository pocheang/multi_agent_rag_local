"""Query routes for the Multi-Agent Local RAG API."""
import asyncio
import logging
from typing import Annotated, Any
from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import StreamingResponse
from app.api.dependencies import (    auth_service,    query_guard,    query_result_cache,    quota_guard,    runtime_metrics,    shadow_queue,    settings,    _require_user,    _require_existing_session_for_query,    _require_permission,    _query_cache_key,    _trace_id,    _run_with_query_runtime,    _maybe_sign_response,    _history_store_for_user,    _memory_store_for_user,    _build_memory_context_for_session,    _promote_long_term_memory,    _allowed_sources_for_user,    _allowed_sources_for_visible_filenames,    _enforce_result_source_scope,    _resynthesize_after_source_scope,    _list_visible_pdf_names_for_user,    _visible_doc_chunks_by_filename_for_user,    _is_file_inventory_question,    _build_user_file_inventory_answer,    _audit,    _normalize_agent_class_hint,    _normalize_retrieval_strategy,    _resolve_effective_agent_class,    _latest_answer_for_same_question,    _launch_shadow_run,    _effective_strategy_for_session,    _sse_response,)
from app.core.schemas import QueryRequest, QueryResponse
from app.graph.streaming import encode_sse, run_query_stream
from app.graph.workflow import run_query
from app.services.alerting import emit_alert
from app.services.consistency_guard import should_stabilize, text_similarity
from app.services.input_normalizer import (    enhance_user_question_for_completion,    normalize_and_validate_user_question,    normalize_user_question,)
from app.services.pdf_agent_guard import (    apply_pdf_focus_to_question,    build_choose_pdf_hint,    build_upload_pdf_hint,    choose_pdf_targets,)
from app.services.query_intent import is_casual_chat_query
from app.services.quota_guard import QuotaExceededError
from app.services.retrieval_profiles import profile_force_local_only, profile_to_strategy
from app.services.runtime_ops import resolve_profile_for_request

router = APIRouter(prefix="/query", tags=["query"])
logger = logging.getLogger(__name__)


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
        raise HTTPException(status_code=429, detail=str(e))
    try:
        normalized_question = normalize_and_validate_user_question(req.question)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
                metadata={"route": "policy", "agent_class": "policy", "web_used": False, "graph_entities": [], "citations": []},
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
        pdf_names = _list_visible_pdf_names_for_user(user)
        if not pdf_names:
            answer = build_upload_pdf_hint()
            _audit(request, action="query.run", resource_type="query", result="success", user=user, detail="pdf_agent_no_pdf")
            if req.session_id:
                history_store = _history_store_for_user(user)
                history_store.append_message(req.session_id, "user", normalized_question)
                history_store.append_message(
                    req.session_id,
                    "assistant",
                    answer,
                    metadata={"route": "pdf_text", "agent_class": "pdf_text", "web_used": False, "graph_entities": [], "citations": []},
                )
            return QueryResponse(
                answer=answer,
                route="pdf_text",
                citations=[],
                graph_entities=[],
                web_used=False,
                debug={"reason": "pdf_agent_no_pdf", "skill": "pdf_text_reader", "agent_class": "pdf_text", "use_reasoning": req.use_reasoning},
            )
        selected_pdfs = choose_pdf_targets(normalized_question, pdf_names)
        if len(pdf_names) > 1 and not selected_pdfs:
            answer = build_choose_pdf_hint(pdf_names)
            _audit(request, action="query.run", resource_type="query", result="success", user=user, detail="pdf_agent_need_selection")
            if req.session_id:
                history_store = _history_store_for_user(user)
                history_store.append_message(req.session_id, "user", normalized_question)
                history_store.append_message(
                    req.session_id,
                    "assistant",
                    answer,
                    metadata={"route": "pdf_text", "agent_class": "pdf_text", "web_used": False, "graph_entities": [], "citations": []},
                )
            return QueryResponse(
                answer=answer,
                route="pdf_text",
                citations=[],
                graph_entities=[],
                web_used=False,
                debug={"reason": "pdf_agent_need_selection", "skill": "pdf_text_reader", "agent_class": "pdf_text", "use_reasoning": req.use_reasoning},
            )
        if selected_pdfs:
            chunks_map = _visible_doc_chunks_by_filename_for_user(user)
            selected_with_chunks = [x for x in selected_pdfs if chunks_map.get(x, 0) > 0]
            if not selected_with_chunks:
                answer = (
                    "The selected document exists, but its index is empty (chunks=0), so I cannot read detailed content yet.\n"
                    "Please click Reindex for this file, then ask again."
                )
                _audit(request, action="query.run", resource_type="query", result="success", user=user, detail="pdf_agent_chunks_zero")
                if req.session_id:
                    history_store = _history_store_for_user(user)
                    history_store.append_message(req.session_id, "user", original_question)
                    history_store.append_message(
                        req.session_id,
                        "assistant",
                        answer,
                        metadata={"route": "pdf_text", "agent_class": "pdf_text", "web_used": False, "graph_entities": [], "citations": []},
                    )
                return QueryResponse(
                    answer=answer,
                    route="pdf_text",
                    citations=[],
                    graph_entities=[],
                    web_used=False,
                    debug={"reason": "pdf_agent_chunks_zero", "skill": "pdf_text_reader", "agent_class": "pdf_text", "use_reasoning": req.use_reasoning},
                )
            normalized_question = apply_pdf_focus_to_question(normalized_question, selected_with_chunks)
            pdf_allowed_sources = _allowed_sources_for_visible_filenames(user, selected_with_chunks)

    is_fast_smalltalk = is_casual_chat_query(normalized_question)
    effective_question = normalized_question if is_fast_smalltalk else enhance_user_question_for_completion(normalized_question)
    memory_context = "" if is_fast_smalltalk else _build_memory_context_for_session(
        user=user,
        session_id=req.session_id,
        question=effective_question,
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
        raise HTTPException(status_code=429, detail=str(e))
    run_query_kwargs: dict[str, Any] = {
        "use_web_fallback": effective_use_web_fallback,
        "use_reasoning": effective_use_reasoning,
        "memory_context": memory_context,
        "allowed_sources": allowed_sources,
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
    cached_response = None if is_fast_smalltalk else query_result_cache.get(cache_key, session_id=req.session_id)
    if isinstance(cached_response, dict) and cached_response:
        try:
            cached = QueryResponse.model_validate(cached_response)
        except Exception:
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
        hot_cached = None if is_fast_smalltalk else query_result_cache.get(cache_key, session_id=req.session_id)
        if isinstance(hot_cached, dict) and hot_cached:
            try:
                return QueryResponse.model_validate(hot_cached)
            except Exception:
                runtime_metrics.inc("query_cache_invalid_total")
        emit_alert(
            "query_duplicate_inflight",
            {"trace_id": _trace_id(request), "session_id": str(req.session_id or "")},
        )
        raise HTTPException(status_code=409, detail="duplicate request in progress")
    def _query_pipeline():
        runtime_kwargs = dict(run_query_kwargs)
        if overload_mode_enabled():
            runtime_kwargs["use_web_fallback"] = False
            runtime_kwargs["use_reasoning"] = False
            runtime_kwargs.setdefault("retrieval_strategy", "baseline")
        result_local = _call_with_supported_kwargs(run_query, effective_question, **runtime_kwargs)
        result_local = _enforce_result_source_scope(result_local, allowed_sources=allowed_sources, request=request, user=user)
        result_local = _resynthesize_after_source_scope(
            result_local,
            question=effective_question,
            memory_context=memory_context,
            use_reasoning=bool(runtime_kwargs.get("use_reasoning", False)),
        )
        consistency_local = {"checked": False}
        if bool(settings.consistency_guard_enabled) and (not is_fast_smalltalk):
            prev_answer = _latest_answer_for_same_question(user=user, session_id=req.session_id, question=original_question)
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
                    retried = _enforce_result_source_scope(retried, allowed_sources=allowed_sources, request=request, user=user)
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
    vector_citations = [Citation(**x) for x in result.get("vector_result", {}).get("citations", [])]
    web_citations = [Citation(**x) for x in result.get("web_result", {}).get("citations", [])]
    conflict_report = detect_evidence_conflict(
        list(result.get("vector_result", {}).get("citations", []) or [])
        + list(result.get("web_result", {}).get("citations", []) or [])
    )
    if conflict_report.get("conflict"):
        result["answer"] = f"[evidence-conflict-warning]\n{result.get('answer', '')}"
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
                "web_used": result.get("web_result", {}).get("used", False),
                "thoughts": result.get("thoughts", []),
                "graph_entities": result.get("graph_result", {}).get("entities", []),
                "citations": result.get("vector_result", {}).get("citations", []) + result.get("web_result", {}).get("citations", []),
                "retrieval_diagnostics": result.get("vector_result", {}).get("retrieval_diagnostics", {}),
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
        "graph_entities": result.get("graph_result", {}).get("entities", []),
        "web_used": result.get("web_result", {}).get("used", False),
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
    query_result_cache.set(cache_key, response.model_dump(), session_id=req.session_id)
    runtime_metrics.inc("query_success_total")
    return response


def _sse_response(generator: Any) -> StreamingResponse:
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


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
        raise HTTPException(status_code=429, detail=str(e))
    try:
        normalized_question = normalize_and_validate_user_question(question)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
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
                metadata={"route": "policy", "agent_class": "policy", "web_used": False, "graph_entities": [], "citations": []},
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

        return _sse_response(event_gen_file_inventory())

    if effective_agent_class == "pdf_text":
        pdf_names = _list_visible_pdf_names_for_user(user)
        selected_pdfs = choose_pdf_targets(normalized_question, pdf_names) if pdf_names else []
        if not pdf_names:
            answer = build_upload_pdf_hint()
            _audit(request, action="query.stream", resource_type="query", result="success", user=user, detail="pdf_agent_no_pdf")
            if session_id:
                history_store = _history_store_for_user(user)
                history_store.append_message(session_id, "user", normalized_question)
                history_store.append_message(
                    session_id,
                    "assistant",
                    answer,
                    metadata={"route": "pdf_text", "agent_class": "pdf_text", "web_used": False, "graph_entities": [], "citations": []},
                )

            def event_gen_pdf_upload_needed():
                yield encode_sse({"type": "status", "message": "pdf_upload_required"})
                yield encode_sse({"type": "answer_chunk", "content": answer})
                yield encode_sse(
                    {
                        "type": "done",
                        "result": {
                            "answer": answer,
                            "route": "pdf_text",
                            "reason": "pdf_agent_no_pdf",
                            "skill": "pdf_text_reader",
                            "agent_class": "pdf_text",
                            "vector_result": {},
                            "graph_result": {},
                            "web_result": {"used": False, "citations": [], "context": ""},
                        },
                    }
                )

            return _sse_response(event_gen_pdf_upload_needed())
        if len(pdf_names) > 1 and not selected_pdfs:
            answer = build_choose_pdf_hint(pdf_names)
            _audit(request, action="query.stream", resource_type="query", result="success", user=user, detail="pdf_agent_need_selection")
            if session_id:
                history_store = _history_store_for_user(user)
                history_store.append_message(session_id, "user", normalized_question)
                history_store.append_message(
                    session_id,
                    "assistant",
                    answer,
                    metadata={"route": "pdf_text", "agent_class": "pdf_text", "web_used": False, "graph_entities": [], "citations": []},
                )

            def event_gen_pdf_select_needed():
                yield encode_sse({"type": "status", "message": "pdf_selection_required"})
                yield encode_sse({"type": "answer_chunk", "content": answer})
                yield encode_sse(
                    {
                        "type": "done",
                        "result": {
                            "answer": answer,
                            "route": "pdf_text",
                            "reason": "pdf_agent_need_selection",
                            "skill": "pdf_text_reader",
                            "agent_class": "pdf_text",
                            "vector_result": {},
                            "graph_result": {},
                            "web_result": {"used": False, "citations": [], "context": ""},
                        },
                    }
                )

            return _sse_response(event_gen_pdf_select_needed())
        if selected_pdfs:
            chunks_map = _visible_doc_chunks_by_filename_for_user(user)
            selected_with_chunks = [x for x in selected_pdfs if chunks_map.get(x, 0) > 0]
            if not selected_with_chunks:
                answer = (
                    "The selected document exists, but its index is empty (chunks=0), so I cannot read detailed content yet.\n"
                    "Please click Reindex for this file, then ask again."
                )
                _audit(request, action="query.stream", resource_type="query", result="success", user=user, detail="pdf_agent_chunks_zero")
                if session_id:
                    history_store = _history_store_for_user(user)
                    history_store.append_message(session_id, "user", original_question)
                    history_store.append_message(
                        session_id,
                        "assistant",
                        answer,
                        metadata={"route": "pdf_text", "agent_class": "pdf_text", "web_used": False, "graph_entities": [], "citations": []},
                    )

                def event_gen_pdf_chunks_zero():
                    yield encode_sse({"type": "status", "message": "pdf_reindex_required"})
                    yield encode_sse({"type": "answer_chunk", "content": answer})
                    yield encode_sse(
                        {
                            "type": "done",
                            "result": {
                                "answer": answer,
                                "route": "pdf_text",
                                "reason": "pdf_agent_chunks_zero",
                                "skill": "pdf_text_reader",
                                "agent_class": "pdf_text",
                                "vector_result": {},
                                "graph_result": {},
                                "web_result": {"used": False, "citations": [], "context": ""},
                            },
                        }
                    )

                return _sse_response(event_gen_pdf_chunks_zero())
            normalized_question = apply_pdf_focus_to_question(normalized_question, selected_with_chunks)
            pdf_allowed_sources = _allowed_sources_for_visible_filenames(user, selected_with_chunks)

    is_fast_smalltalk = is_casual_chat_query(normalized_question)
    effective_question = normalized_question if is_fast_smalltalk else enhance_user_question_for_completion(normalized_question)
    history_store = _history_store_for_user(user)
    memory_context = "" if is_fast_smalltalk else _build_memory_context_for_session(
        user=user,
        session_id=session_id,
        question=effective_question,
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
        raise HTTPException(status_code=429, detail=str(e))
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
            return _sse_response(event_gen_replay())

    cached_stream = None if is_fast_smalltalk else query_result_cache.get(stream_cache_key, session_id=session_id)
    if isinstance(cached_stream, dict) and cached_stream.get("result"):
        runtime_metrics.inc("query_stream_cache_hit_total")
        done_result = dict(cached_stream.get("result", {}) or {})

        async def event_gen_cached():
            yield encode_sse({"type": "status", "message": "cache_hit"})
            answer_text = str(done_result.get("answer", "") or "")
            if answer_text:
                yield encode_sse({"type": "answer_chunk", "content": answer_text})
            yield encode_sse({"type": "done", "result": done_result})

        return _sse_response(event_gen_cached())
    if not query_result_cache.mark_inflight(stream_cache_key):
        runtime_metrics.inc("query_stream_duplicate_total")
        emit_alert(
            "query_stream_duplicate_inflight",
            {"trace_id": _trace_id(request), "session_id": str(session_id or "")},
        )
        raise HTTPException(status_code=409, detail="duplicate request in progress")
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
        raise HTTPException(status_code=400, detail=f"invalid api settings: {e}")

    async def event_gen():
        final_result = None
        trace_id = _trace_id(request)
        stream_kwargs: dict[str, Any] = {
            "use_web_fallback": effective_use_web_fallback,
            "use_reasoning": effective_use_reasoning,
            "memory_context": memory_context,
            "allowed_sources": allowed_sources,
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
                    loop = asyncio.get_running_loop()
                    done_marker: dict[str, Any] = {"type": "__producer_done__"}
                    queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=256)
                    producer_stop = threading.Event()
                    producer_error: dict[str, Exception] = {}

                    def _stream_producer() -> None:
                        try:
                            for _event in _call_with_supported_kwargs(
                                run_query_stream,
                                effective_question,
                                **runtime_stream_kwargs,
                            ):
                                if producer_stop.is_set():
                                    break
                                fut = asyncio.run_coroutine_threadsafe(queue.put(_event), loop)
                                fut.result()
                        except Exception as ex:
                            producer_error["error"] = ex
                        finally:
                            producer_stop.set()
                            asyncio.run_coroutine_threadsafe(queue.put(done_marker), loop).result()

                    producer_context = contextvars.copy_context()
                    threading.Thread(target=lambda: producer_context.run(_stream_producer), daemon=True).start()
                    heartbeat_s = max(2.0, float(getattr(settings, "stream_heartbeat_seconds", 8.0) or 8.0))

                    while True:
                        if await request.is_disconnected():
                            producer_stop.set()
                            break
                        try:
                            event = await asyncio.wait_for(queue.get(), timeout=heartbeat_s)
                        except asyncio.TimeoutError:
                            yield encode_sse({"type": "status", "message": "heartbeat", "trace_id": trace_id})
                            continue
                        if event is done_marker:
                            break
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
                                final_result["answer"] = f"[evidence-conflict-warning]\n{final_result.get('answer', '')}"
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

                    if producer_error.get("error") is not None:
                        raise producer_error["error"]
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
                    "citations": final_result.get("vector_result", {}).get("citations", []) + final_result.get("web_result", {}).get("citations", []),
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
            query_result_cache.set(stream_cache_key, {"result": final_result}, session_id=session_id)
            runtime_metrics.inc("query_stream_success_total")

    return _sse_response(event_gen())
