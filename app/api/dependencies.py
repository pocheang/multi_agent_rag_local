"""
Shared dependencies, services, and helper functions for the QueryMind API.

This module serves as the central hub for all shared dependencies and re-exports
helper functions from specialized utility modules.
"""

import logging
import re
import threading
from typing import Any

from fastapi import Request
from fastapi.security import HTTPBearer

from app.api.utils.admin_helpers import _runtime_diagnostics_summary as _runtime_diagnostics_summary_impl
from app.api.utils.auth_dependencies import (
    _require_permission,
    _require_user,
    _require_user_and_token,
    auth_scheme,
    auth_service,
)
from app.api.utils.auth_helpers import (
    _audit,
)
from app.api.utils.admin_helpers import (
    _check_chroma_ready,
    _check_ollama_ready,
    _extract_grounding_support_from_detail,
    _filter_audit_rows,
    _load_benchmark_queries,
    _parse_audit_ts,
    _parse_request_ts,
)
from app.api.utils.auth_helpers import _clear_auth_cookie, _client_ip, _set_auth_cookie
from app.api.utils.document_helpers import (
    _allowed_sources_for_user,
    _build_user_file_inventory_answer,
    _is_file_inventory_question,
)
from app.api.utils.memory_helpers import _memory_store_for_user, _promote_long_term_memory
from app.api.utils.query_helpers import (
    _call_with_supported_kwargs,
    _normalize_agent_class_hint,
    _query_limiter_key,
    _resolve_effective_agent_class,
    _trace_id,
)
from app.api.utils.response_helpers import _sse_response
from app.api.utils.session_helpers import _require_existing_session_for_query, _require_valid_session_id
from app.api.utils.document_helpers import _enforce_result_source_scope as _enforce_result_source_scope_impl
from app.api.utils.document_helpers import (
    _visible_index_fingerprint_for_user,
)
from app.api.utils.error_responses import bad_request
from app.api.utils.memory_helpers import _build_memory_context_for_session as _build_memory_context_for_session_impl
from app.api.utils.query_helpers import _effective_strategy_for_session as _effective_strategy_for_session_impl
from app.api.utils.query_helpers import _is_overload_mode as _is_overload_mode_impl
from app.api.utils.query_helpers import _launch_shadow_run as _launch_shadow_run_impl
from app.api.utils.query_helpers import _query_cache_key as _query_cache_key_impl
from app.api.utils.query_helpers import _query_model_fingerprint_for_user as _query_model_fingerprint_for_user_impl
from app.api.utils.query_helpers import _run_with_query_runtime as _run_with_query_runtime_impl
from app.api.utils.query_helpers import _user_api_settings_for_runtime as _user_api_settings_for_runtime_impl
from app.api.utils.session_helpers import (
    _history_store_for_user,
)

# Import helper functions from utility modules
from app.api.utils.string_utils import normalize_string
from app.core.config import get_settings
from app.core.schemas import AdminModelSettingsResponse, UserApiSettings, UserApiSettingsView
from app.services.auto_ingest_watcher import AutoIngestWatcher
from app.services.background_queue import BackgroundTaskQueue
from app.services.model_config_store import get_global_model_settings, public_global_model_settings
from app.services.prompt_store import PromptStore
from app.services.query_guard import QueryLoadGuard
from app.services.query_result_cache import QueryResultCache
from app.services.quota_guard import QuotaGuard
from app.services.rate_limiter import SlidingWindowLimiter
from app.services.runtime_metrics import RuntimeMetrics

# Global settings and logger
settings = get_settings()
logger = logging.getLogger(__name__)

# Shared service instances
prompt_store = PromptStore()
auto_ingest_watcher = AutoIngestWatcher(settings=settings)

# Rate limiters
login_limiter = SlidingWindowLimiter(
    max_attempts=settings.auth_login_max_failures,
    window_seconds=settings.auth_login_window_seconds,
)
register_limiter = SlidingWindowLimiter(
    max_attempts=settings.auth_register_max_attempts,
    window_seconds=settings.auth_register_window_seconds,
)
# Upload rate limiter - prevent storage abuse
upload_limiter = SlidingWindowLimiter(
    max_attempts=20,  # 20 uploads per hour per user
    window_seconds=3600,
)

# Query guard and caching
query_guard = QueryLoadGuard(
    per_user_max_requests=settings.query_rate_limit_max_attempts,
    per_user_window_seconds=settings.query_rate_limit_window_seconds,
    max_concurrent=settings.query_max_concurrent,
    max_waiting=settings.query_max_waiting,
    acquire_timeout_ms=settings.query_acquire_timeout_ms,
    backend=settings.query_guard_backend,
)
query_result_cache = QueryResultCache(
    backend=settings.query_result_cache_backend,
    ttl_seconds=settings.query_result_cache_ttl_seconds,
    max_items=settings.query_result_cache_max_items,
    session_ttl_seconds=settings.query_result_session_ttl_seconds,
)
quota_guard = QuotaGuard()

# Background task queue
shadow_queue = BackgroundTaskQueue(
    maxsize=settings.shadow_queue_maxsize,
    workers=settings.shadow_queue_workers,
    name="shadow-query",
)

# Auto-ingest watcher state
_auto_ingest_stop_event = threading.Event()
_auto_ingest_thread: threading.Thread | None = None

# Runtime metrics
runtime_metrics = RuntimeMetrics()



def __getattr__(name: str):
    """Resolve legacy helper imports from split utility modules."""
    from app.api.utils import admin_helpers, auth_dependencies, auth_helpers, document_helpers, memory_helpers, query_helpers, request_helpers, response_helpers, session_helpers

    modules = (
        admin_helpers,
        auth_dependencies,
        auth_helpers,
        document_helpers,
        memory_helpers,
        query_helpers,
        request_helpers,
        session_helpers,
    )
    for module in modules:
        if hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

# ============================================================================
# Dependency-injected helpers
# ============================================================================
#
# The functions below bind module-level singletons (auth_service, query_guard,
# shadow_queue, runtime metrics, ...) to the pure utility helpers in
# ``app.api.utils.*``. The utils layer is kept singleton-free so it remains
# unit-testable; this module is the only place that knows about the live
# dependencies.


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
) -> str:
    """Compute the query cache key, injecting user-scoped fingerprint helpers."""
    return _query_cache_key_impl(
        user=user,
        session_id=session_id,
        question=question,
        use_web_fallback=use_web_fallback,
        use_reasoning=use_reasoning,
        retrieval_strategy=retrieval_strategy,
        agent_class_hint=agent_class_hint,
        request_id=request_id,
        mode=mode,
        index_fingerprint_fn=_visible_index_fingerprint_for_user,
        model_fingerprint_fn=_query_model_fingerprint_for_user,
    )


def _run_with_query_runtime(*, user: dict[str, Any], request: Request, fn):
    """Run ``fn`` under the shared query guard / metrics runtime."""
    return _run_with_query_runtime_impl(
        user=user,
        request=request,
        fn=fn,
        query_guard=query_guard,
        runtime_metrics=runtime_metrics,
        api_settings_fn=_user_api_settings_for_runtime,
    )


def _is_overload_mode() -> bool:
    """Return True when the query guard is currently shedding load."""
    return _is_overload_mode_impl(query_guard)


def _launch_shadow_run(
    *,
    user: dict[str, Any],
    session_id: str | None,
    question: str,
    primary_result: dict[str, Any],
) -> None:
    """Schedule a shadow comparison run on the background queue."""
    return _launch_shadow_run_impl(
        user=user,
        session_id=session_id,
        question=question,
        primary_result=primary_result,
        shadow_queue=shadow_queue,
    )


def _effective_strategy_for_session(
    *, req_strategy: str | None, user: dict[str, Any], session_id: str | None, question: str
) -> tuple[str, dict[str, Any]]:
    """Resolve the strategy to use for a session, honoring strategy locks."""
    return _effective_strategy_for_session_impl(
        req_strategy=req_strategy,
        user=user,
        session_id=session_id,
        question=question,
        history_store_fn=_history_store_for_user,
    )


def _build_memory_context_for_session(user: dict[str, Any], session_id: str | None, question: str) -> str:
    """Build the LLM-ready memory context block for a session."""
    return _build_memory_context_for_session_impl(user, session_id, question, _history_store_for_user)


def _enforce_result_source_scope(
    result: dict[str, Any], allowed_sources: list[str], request: Request, user: dict[str, Any]
) -> dict[str, Any]:
    """Drop citations outside the user's allowed source scope, with audit logging."""
    return _enforce_result_source_scope_impl(result, allowed_sources, request, user, _audit)


def _runtime_diagnostics_summary() -> dict[str, Any]:
    """Compose the runtime diagnostics block surfaced on /admin/* endpoints."""
    from app.api.middleware import get_request_metrics

    return _runtime_diagnostics_summary_impl(get_request_metrics)


def _user_api_settings_for_runtime(user: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve per-user API settings for runtime model selection."""
    return _user_api_settings_for_runtime_impl(user, auth_service)


def _query_model_fingerprint_for_user(user: dict[str, Any]) -> str:
    """Compute a fingerprint of the resolved model config for cache invalidation."""
    return _query_model_fingerprint_for_user_impl(user, auth_service, get_global_model_settings)


# ============================================================================
# Additional helper functions that remain in dependencies.py
# ============================================================================


def _normalize_prompt_fields(title: str, content: str) -> tuple[str, str]:
    """Normalize and validate prompt fields with security checks."""
    t = (title or "").strip()
    c = (content or "").strip()

    # Required field validation
    if not t:
        raise bad_request("title is required")
    if not c:
        raise bad_request("content is required")

    # Length validation (aligned with frontend limits)
    if len(t) > 200:
        raise bad_request("title must be under 200 characters")
    if len(c) > 50000:
        raise bad_request("content must be under 50000 characters")

    # Security: Remove dangerous characters that could lead to XSS
    # Remove HTML tags and script-related patterns
    t = re.sub(r"<[^>]*>", "", t)
    t = re.sub(r"javascript:", "", t, flags=re.IGNORECASE)
    t = re.sub(r"on\w+\s*=", "", t, flags=re.IGNORECASE)

    c = re.sub(r"<script[^>]*>.*?</script>", "", c, flags=re.IGNORECASE | re.DOTALL)
    c = re.sub(r"javascript:", "", c, flags=re.IGNORECASE)
    c = re.sub(r"on\w+\s*=", "", c, flags=re.IGNORECASE)

    # Final trim after sanitization
    t = t.strip()
    c = c.strip()

    # Recheck after sanitization
    if not t or not c:
        raise bad_request("invalid content after sanitization")

    return t, c


def _mask_api_key(api_key: str) -> str:
    """Mask an API key for display."""
    value = str(api_key or "").strip()
    if not value:
        return ""
    if len(value) <= 8:
        return "*" * len(value)
    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"


def _api_settings_view(settings_data: UserApiSettings) -> UserApiSettingsView:
    """Convert API settings to view model."""
    from app.core.schemas import UserApiSettingsView

    global_settings = get_global_model_settings()
    global_enabled = bool(global_settings.get("enabled", False))

    global_provider = global_settings.get("provider") if global_enabled else None
    global_model = global_settings.get("chat_model") if global_enabled else None

    if global_enabled:
        effective_provider = global_settings.get("provider", "local")
        effective_model = global_settings.get("chat_model", "")
    else:
        effective_provider = settings_data.provider
        effective_model = settings_data.model

    return UserApiSettingsView(
        provider=normalize_string(settings_data.provider, lowercase=True) or "local",
        api_key_masked=_mask_api_key(settings_data.api_key),
        base_url=str(settings_data.base_url or "").strip(),
        model=str(settings_data.model or "").strip(),
        temperature=float(settings_data.temperature),
        max_tokens=int(settings_data.max_tokens),
        global_override_enabled=global_enabled,
        global_provider=global_provider,
        global_model=global_model,
        effective_provider=effective_provider,
        effective_model=effective_model,
    )


def _admin_model_settings_view(settings_data: dict[str, Any]) -> AdminModelSettingsResponse:
    """Convert model settings to admin view model."""
    return AdminModelSettingsResponse(ok=True, settings=public_global_model_settings(settings_data))


