"""
Query-related helper functions for the QueryMind API.
"""

import hashlib
import inspect
import json
import time
import uuid
from typing import Any

from fastapi import Request

from app.api.utils.error_responses import bad_request, internal_error, rate_limited
from app.api.utils.string_utils import normalize_string
from app.core.config import get_settings
from app.graph.workflow import run_query
from app.services.agent_classifier import classify_agent_class
from app.services.alerting import emit_alert
from app.services.consistency_guard import text_similarity
from app.services.network_security import OutboundURLValidationError, validate_api_base_url_for_provider
from app.services.query_guard import QueryOverloadedError, QueryRateLimitedError
from app.services.query_result_cache import QueryResultCache
from app.services.rag_runtime_scope import query_model_fingerprint
from app.services.request_context import request_context
from app.services.retrieval_profiles import normalize_retrieval_profile
from app.services.retry_policy import call_with_retry
from app.services.runtime_ops import append_shadow_run, choose_shadow, resolve_profile_for_request

settings = get_settings()


def _query_limiter_key(user: dict[str, Any], request: Request) -> str:
    """Generate a rate limiter key for the user."""
    user_id = str(user.get("user_id", "") or "").strip()
    if user_id:
        return f"user:{user_id}"
    host = str(getattr(request.client, "host", "") or "").strip()
    return f"ip:{host or 'unknown'}"


def _is_overload_mode(query_guard) -> bool:
    """Check if the system is in overload mode."""
    stats = query_guard.stats()
    return (
        int(stats.get("inflight", 0))
        >= int(getattr(settings, "query_overload_inflight_threshold", settings.query_max_concurrent))
    ) or (
        int(stats.get("waiting", 0))
        >= int(getattr(settings, "query_overload_waiting_threshold", settings.query_max_waiting))
    )


def _query_cache_key(
    *,
    user: dict[str, Any],
    session_id: str | None,
    question: str,
    use_web_fallback: bool,
    use_reasoning: bool,
    retrieval_strategy: str | None,
    agent_class_hint: str | None,
    request_id: str | None,
    mode: str = "query",
    index_fingerprint_fn,
    model_fingerprint_fn,
) -> str:
    """Build a cache key for query results."""
    index_fingerprint = index_fingerprint_fn(user)
    model_fingerprint = model_fingerprint_fn(user)
    cache_fingerprint = hashlib.sha256(
        json.dumps(
            {"index": index_fingerprint, "model": model_fingerprint},
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()
    return QueryResultCache.build_key(
        user_id=str(user.get("user_id", "")),
        session_id=str(session_id or ""),
        question=str(question or ""),
        use_web_fallback=bool(use_web_fallback),
        use_reasoning=bool(use_reasoning),
        retrieval_strategy=str(retrieval_strategy or ""),
        agent_class_hint=str(agent_class_hint or ""),
        mode=mode,
        request_id=str(request_id or ""),
        include_request_id=False,
        index_fingerprint=cache_fingerprint,
    )


def _trace_id(request: Request) -> str:
    """Get or generate a trace ID for the request."""
    return str(getattr(request.state, "trace_id", "") or "").strip() or uuid.uuid4().hex


def _call_with_supported_kwargs(fn, /, *args, **kwargs):
    """Call a function with only the kwargs it supports."""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return fn(*args, **kwargs)
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return fn(*args, **kwargs)
    filtered_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}
    return fn(*args, **filtered_kwargs)


def _run_with_query_runtime(
    *,
    user: dict[str, Any],
    request: Request,
    fn,
    query_guard,
    runtime_metrics,
    api_settings_fn,
):
    """Execute a function within query runtime context."""
    limiter_key = _query_limiter_key(user, request)
    try:
        api_settings = api_settings_fn(user)
    except OutboundURLValidationError as e:
        runtime_metrics.inc("query_invalid_api_settings_total")
        emit_alert(
            "query_invalid_api_settings",
            {
                "trace_id": _trace_id(request),
                "user_id": str(user.get("user_id", "")),
                "reason": str(e),
            },
        )
        raise bad_request(f"invalid api settings: {e}")
    try:
        with query_guard.acquire(limiter_key):
            with request_context(
                timeout_ms=int(getattr(settings, "query_request_timeout_ms", 20000) or 20000),
                overload_mode=_is_overload_mode(query_guard),
                api_settings=api_settings,
            ):
                return call_with_retry("query.runtime", fn)
    except QueryRateLimitedError as e:
        runtime_metrics.inc("query_rate_limited_total")
        emit_alert(
            "query_rate_limited",
            {
                "message": str(e),
                "path": str(request.url.path),
                "trace_id": _trace_id(request),
            },
        )
        raise rate_limited(str(e))
    except QueryOverloadedError as e:
        runtime_metrics.inc("query_overloaded_total")
        emit_alert(
            "query_overloaded",
            {
                "message": str(e),
                "path": str(request.url.path),
                "trace_id": _trace_id(request),
            },
        )
        raise internal_error(str(e))


def _user_api_settings_for_runtime(user: dict[str, Any], auth_service) -> dict[str, Any] | None:
    """Get user API settings for runtime."""
    user_id = str(user.get("user_id", "") or "").strip()
    if not user_id:
        return None
    settings_data = auth_service.get_user_metadata(user_id, "api_settings")
    if not isinstance(settings_data, dict):
        return None
    provider = str(settings_data.get("provider", "") or "").strip().lower()
    if provider:
        settings_data["provider"] = provider
    base_url = str(settings_data.get("base_url", "") or "").strip()
    if base_url and provider:
        settings_data["base_url"] = validate_api_base_url_for_provider(base_url, provider=provider)
    return dict(settings_data)


def _query_model_fingerprint_for_user(user: dict[str, Any], auth_service, get_global_model_settings_fn) -> str:
    """Generate a model fingerprint for the user."""
    user_id = str(user.get("user_id", "") or "").strip()
    user_api_settings = auth_service.get_user_metadata(user_id, "api_settings") if user_id else None
    return query_model_fingerprint(
        user_api_settings=user_api_settings if isinstance(user_api_settings, dict) else None,
        global_model_settings=get_global_model_settings_fn(),
        app_settings=settings,
    )


_ALLOWED_AGENT_CLASSES = {"general", "cybersecurity", "artificial_intelligence", "pdf_text", "policy"}
_ALLOWED_RETRIEVAL_STRATEGIES = {"baseline", "advanced", "safe"}


def _normalize_agent_class_hint(value: str | None) -> str | None:
    """Normalize agent class hint."""
    hint = normalize_string(value, lowercase=True)
    if hint in _ALLOWED_AGENT_CLASSES:
        return hint
    return None


def _normalize_retrieval_strategy(value: str | None) -> str | None:
    """Normalize retrieval strategy."""
    strategy = normalize_string(value, lowercase=True)
    if strategy in _ALLOWED_RETRIEVAL_STRATEGIES:
        return normalize_retrieval_profile(strategy)
    return normalize_retrieval_profile(None)


def _resolve_effective_agent_class(question: str, agent_class_hint: str | None) -> str:
    """Resolve the effective agent class for a query."""
    hinted = _normalize_agent_class_hint(agent_class_hint)
    if hinted:
        return hinted
    guessed = classify_agent_class(question)
    return guessed if guessed in _ALLOWED_AGENT_CLASSES else "general"


def _effective_strategy_for_session(
    *,
    req_strategy: str | None,
    user: dict[str, Any],
    session_id: str | None,
    question: str,
    history_store_fn,
) -> tuple[str, dict[str, Any]]:
    """Determine the effective retrieval strategy for a session."""
    if req_strategy is not None:
        requested = _normalize_retrieval_strategy(req_strategy)
        return resolve_profile_for_request(
            requested,
            user_id=str(user.get("user_id", "")),
            session_id=str(session_id or ""),
            question=question,
        )
    lock = None
    if session_id:
        lock = history_store_fn(user).get_session_strategy_lock(session_id)
    if lock:
        return normalize_retrieval_profile(lock), {"reason": "session_lock", "bucket": None}
    return resolve_profile_for_request(
        None,
        user_id=str(user.get("user_id", "")),
        session_id=str(session_id or ""),
        question=question,
    )


def _launch_shadow_run(
    *,
    user: dict[str, Any],
    session_id: str | None,
    question: str,
    primary_result: dict[str, Any],
    shadow_queue,
) -> None:
    """Launch a shadow query run for comparison."""
    enabled, strategy = choose_shadow(
        user_id=str(user.get("user_id", "")),
        session_id=str(session_id or ""),
        question=question,
    )
    if not enabled or not strategy:
        return

    def _worker():
        started = time.perf_counter()
        try:
            shadow = run_query(
                question,
                use_web_fallback=True,
                use_reasoning=False,
                retrieval_strategy=strategy,
            )
            latency_ms = (time.perf_counter() - started) * 1000.0
            sim = text_similarity(str(primary_result.get("answer", "") or ""), str(shadow.get("answer", "") or ""))
            append_shadow_run(
                {
                    "user_id": str(user.get("user_id", "")),
                    "session_id": str(session_id or ""),
                    "strategy": strategy,
                    "latency_ms": round(latency_ms, 2),
                    "answer_similarity": round(float(sim), 4),
                    "primary_grounding": float(
                        (primary_result.get("grounding", {}) or {}).get("support_ratio", 0.0) or 0.0
                    ),
                    "shadow_grounding": float((shadow.get("grounding", {}) or {}).get("support_ratio", 0.0) or 0.0),
                }
            )
        except Exception as e:
            append_shadow_run(
                {
                    "user_id": str(user.get("user_id", "")),
                    "session_id": str(session_id or ""),
                    "strategy": strategy,
                    "error": f"{type(e).__name__}",
                }
            )

    accepted = shadow_queue.submit(_worker)
    if not accepted:
        append_shadow_run(
            {
                "user_id": str(user.get("user_id", "")),
                "session_id": str(session_id or ""),
                "strategy": strategy,
                "error": "shadow_queue_full",
            }
        )


def handle_pdf_agent_routing(
    normalized_question: str,
    user: dict[str, Any],
    session_id: str | None,
    request: Request,
    action_name: str = "query.run",
) -> tuple[str | None, list[str] | None, dict[str, Any] | None]:
    """
    Handle PDF agent routing logic with all necessary checks.

    Returns:
        (modified_question, pdf_allowed_sources, early_response_dict)
        - If early_response_dict is not None, caller should return immediately
        - Otherwise use modified_question and pdf_allowed_sources for query
    """
    from app.api.dependencies import (
        _allowed_sources_for_filenames,
        _audit,
        _history_store_for_user,
        _list_visible_pdf_names_for_user,
        _visible_doc_chunks_by_filename_for_user,
    )
    from app.services.pdf_agent_guard import (
        apply_pdf_focus_to_question,
        build_choose_pdf_hint,
        build_upload_pdf_hint,
        choose_pdf_targets,
    )

    pdf_names = _list_visible_pdf_names_for_user(user)

    # Case 1: No PDFs uploaded
    if not pdf_names:
        answer = build_upload_pdf_hint()
        _audit(
            request, action=action_name, resource_type="query", result="success", user=user, detail="pdf_agent_no_pdf"
        )
        if session_id:
            history_store = _history_store_for_user(user)
            history_store.append_message(session_id, "user", normalized_question)
            history_store.append_message(
                session_id,
                "assistant",
                answer,
                metadata={
                    "route": "pdf_text",
                    "agent_class": "pdf_text",
                    "web_used": False,
                    "graph_entities": [],
                    "citations": [],
                },
            )
        return (
            None,
            None,
            {
                "answer": answer,
                "route": "pdf_text",
                "reason": "pdf_agent_no_pdf",
                "skill": "pdf_text_reader",
                "agent_class": "pdf_text",
            },
        )

    # Case 2: Multiple PDFs but none selected
    selected_pdfs = choose_pdf_targets(normalized_question, pdf_names)
    if len(pdf_names) > 1 and not selected_pdfs:
        answer = build_choose_pdf_hint(pdf_names)
        _audit(
            request,
            action=action_name,
            resource_type="query",
            result="success",
            user=user,
            detail="pdf_agent_need_selection",
        )
        if session_id:
            history_store = _history_store_for_user(user)
            history_store.append_message(session_id, "user", normalized_question)
            history_store.append_message(
                session_id,
                "assistant",
                answer,
                metadata={
                    "route": "pdf_text",
                    "agent_class": "pdf_text",
                    "web_used": False,
                    "graph_entities": [],
                    "citations": [],
                },
            )
        return (
            None,
            None,
            {
                "answer": answer,
                "route": "pdf_text",
                "reason": "pdf_agent_need_selection",
                "skill": "pdf_text_reader",
                "agent_class": "pdf_text",
            },
        )

    # Case 3: Selected PDFs but no chunks
    if selected_pdfs:
        chunks_map = _visible_doc_chunks_by_filename_for_user(user)
        selected_with_chunks = [x for x in selected_pdfs if chunks_map.get(x, 0) > 0]
        if not selected_with_chunks:
            answer = (
                "The selected document exists, but its index is empty (chunks=0), so I cannot read detailed content yet.\n"
                "Please click Reindex for this file, then ask again."
            )
            _audit(
                request,
                action=action_name,
                resource_type="query",
                result="success",
                user=user,
                detail="pdf_agent_chunks_zero",
            )
            if session_id:
                history_store = _history_store_for_user(user)
                history_store.append_message(session_id, "user", normalized_question)
                history_store.append_message(
                    session_id,
                    "assistant",
                    answer,
                    metadata={
                        "route": "pdf_text",
                        "agent_class": "pdf_text",
                        "web_used": False,
                        "graph_entities": [],
                        "citations": [],
                    },
                )
            return (
                None,
                None,
                {
                    "answer": answer,
                    "route": "pdf_text",
                    "reason": "pdf_agent_chunks_zero",
                    "skill": "pdf_text_reader",
                    "agent_class": "pdf_text",
                },
            )

        # Case 4: Success - apply PDF focus
        modified_question = apply_pdf_focus_to_question(normalized_question, selected_with_chunks)
        pdf_allowed_sources = _allowed_sources_for_filenames(user, selected_with_chunks)
        return modified_question, pdf_allowed_sources, None

    # No selection needed (single PDF or auto-selected)
    return normalized_question, None, None
