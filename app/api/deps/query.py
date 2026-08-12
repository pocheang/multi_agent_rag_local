"""
Query-related helper functions for the QueryMind API.
"""

import hashlib
import inspect
import json
import uuid
from typing import Any

from fastapi import Request

from app.api.transport.errors import bad_request, internal_error, rate_limited
from app.core.config import get_settings
from app.orchestration.shadow import RuntimeShadowObservationSink, ShadowRunner, load_shadow_rollout
from app.orchestration.standard_request_policy import (
    effective_strategy_for_session as _effective_strategy_for_session_policy,
)
from app.orchestration.standard_request_policy import (
    normalize_agent_class_hint as _normalize_agent_class_hint_policy,
)
from app.orchestration.standard_request_policy import (
    normalize_retrieval_strategy as _normalize_retrieval_strategy_policy,
)
from app.orchestration.standard_request_policy import (
    resolve_effective_agent_class as _resolve_effective_agent_class_policy,
)
from app.pipeline.contracts import PipelineRequest, PipelineResult, PipelineRoute, PipelineUser
from app.pipeline.profiles import PipelineProfile
from app.pipeline.rag_pipeline import RAGPipeline
from app.services.models.config_store import normalize_persisted_temperature
from app.services.observability.alerting import emit_alert
from app.services.query_guard import QueryOverloadedError, QueryRateLimitedError
from app.services.runtime.query_result_cache import QueryResultCache
from app.services.runtime.rag_runtime_scope import query_model_fingerprint
from app.services.runtime.request_context import request_context
from app.services.security.network import OutboundURLValidationError, validate_api_base_url_for_provider

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
                # Retry ownership belongs to the typed request/Engine contract;
                # the HTTP boundary must not allocate an independent budget.
                return fn()
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
    settings_data["temperature"] = normalize_persisted_temperature(settings_data.get("temperature", 0.7))
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


def _normalize_agent_class_hint(value: str | None) -> str | None:
    """Compatibility delegate for the canonical standard-request policy."""
    return _normalize_agent_class_hint_policy(value)


def _normalize_retrieval_strategy(value: str | None) -> str | None:
    """Compatibility delegate for the canonical standard-request policy."""
    return _normalize_retrieval_strategy_policy(value)


def _resolve_effective_agent_class(question: str, agent_class_hint: str | None) -> str:
    """Compatibility delegate for the canonical standard-request policy."""
    return _resolve_effective_agent_class_policy(question, agent_class_hint)


def _effective_strategy_for_session(
    *,
    req_strategy: str | None,
    user: dict[str, Any],
    session_id: str | None,
    question: str,
    history_store_fn,
) -> tuple[str, dict[str, Any]]:
    """Compatibility delegate for the canonical standard-request policy."""
    return _effective_strategy_for_session_policy(
        req_strategy=req_strategy,
        user=user,
        session_id=session_id,
        question=question,
        history_store_fn=history_store_fn,
    )


def _launch_shadow_run(
    *,
    user: dict[str, Any],
    session_id: str | None,
    question: str,
    primary_result: dict[str, Any],
    shadow_queue,
) -> None:
    """Keep the old helper name while routing candidate work through RAGPipeline."""
    grounding = primary_result.get("grounding", {})
    support_ratio = grounding.get("support_ratio", 0.0) if isinstance(grounding, dict) else 0.0
    primary = PipelineResult(
        answer=str(primary_result.get("answer", "") or ""),
        route=PipelineRoute(route=str(primary_result.get("route", "unknown") or "unknown")),
        quality_report={"grounding_support_ratio": support_ratio},
    )
    pipeline_request = PipelineRequest(
        question=question,
        profile=PipelineProfile.STANDARD,
        session_id=session_id,
        user=PipelineUser(
            user_id=str(user.get("user_id", "") or "") or None,
            username=str(user.get("username", "") or "") or None,
            role=str(user.get("role", "") or "") or None,
            permissions=frozenset(user.get("permissions") or []),
        ),
    )
    ShadowRunner(
        rollout=load_shadow_rollout(),
        queue=shadow_queue,
        sink=RuntimeShadowObservationSink(),
        candidate_pipeline_factory=RAGPipeline,
    ).submit(primary=primary, request=pipeline_request)
