"""
Shared dependencies, services, and helper functions for the QueryMind API.

This module serves as the central hub for all shared dependencies and re-exports
helper functions from specialized utility modules.
"""

import logging
import re
import threading
from dataclasses import dataclass
from typing import Any

from fastapi import Request

from app.api.deps.admin import _runtime_diagnostics_summary as _runtime_diagnostics_summary_impl
from app.api.deps.auth import (
    auth_service,
)
from app.api.deps.documents import _enforce_result_source_scope as _enforce_result_source_scope_impl
from app.api.deps.documents import (
    _visible_index_fingerprint_for_user,
)
from app.api.deps.query import _effective_strategy_for_session as _effective_strategy_for_session_impl
from app.api.deps.query import _is_overload_mode as _is_overload_mode_impl
from app.api.deps.query import _launch_shadow_run as _launch_shadow_run_impl
from app.api.deps.query import _query_cache_key as _query_cache_key_impl
from app.api.deps.query import _query_model_fingerprint_for_user as _query_model_fingerprint_for_user_impl
from app.api.deps.query import _run_with_query_runtime as _run_with_query_runtime_impl
from app.api.deps.query import _user_api_settings_for_runtime as _user_api_settings_for_runtime_impl
from app.api.deps.sessions import (
    _history_store_for_user,
)
from app.api.schemas import AdminModelSettingsResponse, UserApiSettings, UserApiSettingsView
from app.api.transport.errors import bad_request, forbidden
from app.api.utils.auth_helpers import (
    _audit,
)
from app.api.utils.memory_helpers import _build_memory_context_for_session as _build_memory_context_for_session_impl

# Import helper functions from utility modules
from app.api.utils.string_utils import normalize_string
from app.core.config import Settings, get_settings
from app.services.auth.user_manager import InsufficientCreditsError
from app.services.auto_ingest_watcher import AutoIngestWatcher
from app.services.models.config_store import get_global_model_settings, public_global_model_settings
from app.services.prompts.store import PromptStore
from app.services.query_guard import QueryLoadGuard
from app.services.runtime.background_queue import BackgroundTaskQueue
from app.services.runtime.query_result_cache import QueryResultCache
from app.services.runtime.runtime_metrics import RuntimeMetrics
from app.services.security.quota import QuotaGuard
from app.services.security.rate_limiter import SlidingWindowLimiter

# Global settings and logger
settings = get_settings()
logger = logging.getLogger(__name__)


def _reserve_chat_credit(request: Request, user: dict[str, Any], resource_type: str):
    """Reserve one chat credit or return a stable quota error to the client."""
    try:
        return auth_service.chat_credit_reservation(str(user.get("user_id", "")))
    except InsufficientCreditsError as exc:
        _audit(
            request,
            action="query.credit_reserve",
            resource_type=resource_type,
            result="blocked",
            user=user,
            detail="credit_balance_exhausted",
        )
        raise forbidden(str(exc)) from exc


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


@dataclass(frozen=True, slots=True)
class QueryRuntime:
    """Atomically replaceable services used by query request paths."""

    settings: Settings
    query_guard: QueryLoadGuard
    query_result_cache: QueryResultCache
    quota_guard: QuotaGuard
    shadow_queue: BackgroundTaskQueue


def _build_query_runtime(new_settings: Settings) -> QueryRuntime:
    return QueryRuntime(
        settings=new_settings,
        query_guard=QueryLoadGuard(
            per_user_max_requests=new_settings.query_rate_limit_max_attempts,
            per_user_window_seconds=new_settings.query_rate_limit_window_seconds,
            max_concurrent=new_settings.query_max_concurrent,
            max_waiting=new_settings.query_max_waiting,
            acquire_timeout_ms=new_settings.query_acquire_timeout_ms,
            backend=new_settings.query_guard_backend,
        ),
        query_result_cache=QueryResultCache(
            backend=new_settings.query_result_cache_backend,
            ttl_seconds=new_settings.query_result_cache_ttl_seconds,
            max_items=new_settings.query_result_cache_max_items,
            session_ttl_seconds=new_settings.query_result_session_ttl_seconds,
        ),
        quota_guard=QuotaGuard(),
        shadow_queue=BackgroundTaskQueue(
            maxsize=new_settings.shadow_queue_maxsize,
            workers=new_settings.shadow_queue_workers,
            name="shadow-query",
        ),
    )


_query_runtime = _build_query_runtime(settings)
_runtime_reload_lock = threading.Lock()


def get_query_runtime() -> QueryRuntime:
    """Return one internally consistent snapshot of the query runtime."""
    return _query_runtime


def reload_query_runtime(new_settings: Settings) -> QueryRuntime:
    """Replace query services without stopping the healthy runtime first."""
    global _query_runtime, settings

    new_runtime = _build_query_runtime(new_settings)
    try:
        new_runtime.shadow_queue.start()
    except Exception:
        new_runtime.shadow_queue.stop(timeout=1.0)
        raise

    with _runtime_reload_lock:
        old_runtime = _query_runtime
        _query_runtime = new_runtime
        settings = new_settings
        auto_ingest_watcher.settings = new_settings

    old_runtime.shadow_queue.stop(timeout=1.0)
    return new_runtime


# Auto-ingest watcher state
_auto_ingest_stop_event = threading.Event()
_auto_ingest_thread: threading.Thread | None = None

# Runtime metrics
runtime_metrics = RuntimeMetrics()


def __getattr__(name: str):
    """Resolve legacy helper imports from split utility modules."""
    runtime_attributes = {
        "query_guard": "query_guard",
        "query_result_cache": "query_result_cache",
        "quota_guard": "quota_guard",
        "shadow_queue": "shadow_queue",
    }
    if name in runtime_attributes:
        return getattr(_query_runtime, runtime_attributes[name])

    from app.api.utils import (
        admin_helpers,
        auth_dependencies,
        auth_helpers,
        document_helpers,
        memory_helpers,
        query_helpers,
        request_helpers,
        session_helpers,
    )

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
    conversation: Any = None,
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
        conversation=conversation,
        index_fingerprint_fn=_visible_index_fingerprint_for_user,
        model_fingerprint_fn=_query_model_fingerprint_for_user,
    )


def _run_with_query_runtime(
    *,
    user: dict[str, Any],
    request: Request,
    fn,
    runtime: QueryRuntime | None = None,
):
    """Run ``fn`` under the shared query guard / metrics runtime."""
    runtime = runtime or get_query_runtime()
    return _run_with_query_runtime_impl(
        user=user,
        request=request,
        fn=fn,
        query_guard=runtime.query_guard,
        runtime_metrics=runtime_metrics,
        api_settings_fn=_user_api_settings_for_runtime,
    )


def _is_overload_mode(runtime: QueryRuntime | None = None) -> bool:
    """Return True when the query guard is currently shedding load."""
    runtime = runtime or get_query_runtime()
    return _is_overload_mode_impl(runtime.query_guard)


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
        shadow_queue=get_query_runtime().shadow_queue,
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
    from app.api.transport.middleware import get_request_metrics

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
    from app.api.schemas import UserApiSettingsView

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
