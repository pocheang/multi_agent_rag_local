"""
Shared dependencies, services, and helper functions for the QueryMind API.

This module serves as the central hub for all shared dependencies and re-exports
helper functions from specialized utility modules.
"""

import asyncio
import logging
import re
import sys
import threading
import uuid
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass
from typing import Any

from fastapi import Request

from app.api.deps.admin import _runtime_diagnostics_summary as _runtime_diagnostics_summary_impl
from app.api.deps.auth import (
    auth_service,
)
from app.api.deps.sessions import (
    _history_store_for_user,
)
from app.api.schemas import AdminModelSettingsResponse, UserApiSettings, UserApiSettingsView
from app.api.transport.errors import bad_request, forbidden, rate_limited, service_unavailable
from app.api.utils.auth_helpers import (
    _audit,
)
from app.api.utils.memory_helpers import _build_memory_context_for_session as _build_memory_context_for_session_impl

# Import helper functions from utility modules
from app.api.utils.string_utils import normalize_string
from app.core.config import Settings, get_settings
from app.services.agent_classifier import classify_agent_class
from app.services.auth.user_manager import InsufficientCreditsError
from app.services.auto_ingest_watcher import AutoIngestWatcher
from app.services.models.config_store import get_global_model_settings, public_global_model_settings
from app.services.prompts.store import PromptStore
from app.services.query.guard import QueryOverloadedError, QueryRateLimitedError
from app.services.query_guard import QueryLoadGuard
from app.services.runtime.background_queue import BackgroundTaskQueue
from app.services.runtime.runtime_metrics import RuntimeMetrics
from app.services.security.quota import QuotaGuard
from app.services.security.rate_limiter import SlidingWindowLimiter

# Global settings and logger
settings = get_settings()
logger = logging.getLogger(__name__)


@contextmanager
def _reserve_chat_credit(request: Request, user: dict[str, Any], resource_type: str):
    """Acquire the query load guard, then reserve one chat credit.

    Composes both gates every query entry point needs: per-user rate limiting
    plus bounded server-wide concurrency (``QueryLoadGuard``), and the
    existing per-user credit balance check.
    """
    user_key = str(user.get("user_id", "") or "") or "anonymous"
    try:
        with get_query_runtime().query_guard.acquire(user_key):
            with auth_service.chat_credit_reservation(str(user.get("user_id", ""))) as credit:
                yield credit
    except (QueryRateLimitedError, QueryOverloadedError) as exc:
        _audit(
            request,
            action="query.load_guard",
            resource_type=resource_type,
            result="blocked",
            user=user,
            detail=str(exc),
        )
        if isinstance(exc, QueryRateLimitedError):
            raise rate_limited(str(exc)) from exc
        raise service_unavailable(str(exc)) from exc
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


@asynccontextmanager
async def _reserve_chat_credit_async(request: Request, user: dict[str, Any], resource_type: str):
    """Async twin of ``_reserve_chat_credit`` for async route handlers.

    ``_reserve_chat_credit`` waits on a threading semaphore (up to
    ``QUERY_ACQUIRE_TIMEOUT_MS``) and touches SQLite for the credit reservation;
    both must stay off the event loop or an overloaded server stops answering
    everything, including health checks.  Sync handlers -- the message-rerun path
    -- keep using the sync version, which FastAPI already runs in a threadpool.
    """
    manager = _reserve_chat_credit(request, user, resource_type)
    credit = await asyncio.to_thread(manager.__enter__)
    exc_info: tuple = (None, None, None)
    try:
        yield credit
    except BaseException:
        exc_info = sys.exc_info()
        raise
    finally:
        await asyncio.to_thread(manager.__exit__, *exc_info)


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
        request_helpers,
        session_helpers,
    )

    modules = (
        admin_helpers,
        auth_dependencies,
        auth_helpers,
        document_helpers,
        memory_helpers,
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


def _build_memory_context_for_session(user: dict[str, Any], session_id: str | None, question: str) -> str:
    """Build the LLM-ready memory context block for a session."""
    return _build_memory_context_for_session_impl(user, session_id, question, _history_store_for_user)


def _runtime_diagnostics_summary() -> dict[str, Any]:
    """Compose the runtime diagnostics block surfaced on /admin/* endpoints."""
    from app.api.transport.middleware import get_request_metrics

    return _runtime_diagnostics_summary_impl(get_request_metrics)


def _trace_id(request: Request) -> str:
    """Get or generate a trace ID for the request."""
    return str(getattr(request.state, "trace_id", "") or "").strip() or uuid.uuid4().hex


_ALLOWED_AGENT_CLASSES = {"general", "cybersecurity", "artificial_intelligence", "pdf_text", "policy"}


def _normalize_agent_class_hint(value: str | None) -> str | None:
    """Normalize a public agent-class hint against the allowed class set."""
    hint = normalize_string(value, lowercase=True)
    return hint if hint in _ALLOWED_AGENT_CLASSES else None


def _resolve_effective_agent_class(question: str, agent_class_hint: str | None) -> str:
    """Resolve the canonical agent class for a question, honoring an explicit hint."""
    hinted = _normalize_agent_class_hint(agent_class_hint)
    if hinted:
        return hinted
    guessed = classify_agent_class(question)
    return guessed if guessed in _ALLOWED_AGENT_CLASSES else "general"


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
