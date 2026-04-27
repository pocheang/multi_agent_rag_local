"""
Query-related helper functions for the Multi-Agent Local RAG API.
"""
import hashlib
import inspect
import json
import time
import uuid
from typing import Any

from fastapi import HTTPException, Request

from app.core.config import get_settings
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
from app.services.runtime_ops import resolve_profile_for_request, choose_shadow, append_shadow_run
from app.graph.workflow import run_query

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
        raise HTTPException(status_code=400, detail=f"invalid api settings: {e}")
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
        raise HTTPException(status_code=429, detail=str(e))
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
        raise HTTPException(status_code=503, detail=str(e))


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
    hint = str(value or "").strip().lower()
    if hint in _ALLOWED_AGENT_CLASSES:
        return hint
    return None


def _normalize_retrieval_strategy(value: str | None) -> str | None:
    """Normalize retrieval strategy."""
    strategy = str(value or "").strip().lower()
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
                    "primary_grounding": float((primary_result.get("grounding", {}) or {}).get("support_ratio", 0.0) or 0.0),
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
