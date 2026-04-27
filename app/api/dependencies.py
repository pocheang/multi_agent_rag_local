"""
Shared dependencies, services, and helper functions for the Multi-Agent Local RAG API.

This module serves as the central hub for all shared dependencies and re-exports
helper functions from specialized utility modules.
"""

from pathlib import Path
import hashlib
import hmac
import inspect
import json
import logging
import os
import re
import socket
import sys
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

import httpx

from fastapi import Depends, HTTPException, Request, Response, status
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings
from app.core.schemas import AdminModelSettingsResponse, UserApiSettings, UserApiSettingsView
from app.ingestion.loaders import IMAGE_EXTENSIONS
from app.services.auth_db import AuthDBService
from app.services.auto_ingest_watcher import AutoIngestWatcher
from app.services.background_queue import BackgroundTaskQueue
from app.services.alerting import emit_alert, sign_payload, resolve_signing_secret
from app.services.history import HistoryStore, validate_session_id
from app.services.index_manager import list_indexed_files
from app.services.memory_store import MemoryStore, build_memory_context
from app.services.model_config_store import get_global_model_settings, public_global_model_settings
from app.services.network_security import OutboundURLValidationError, validate_api_base_url_for_provider
from app.services.prompt_store import PromptStore
from app.services.query_guard import QueryLoadGuard, QueryOverloadedError, QueryRateLimitedError
from app.services.query_result_cache import QueryResultCache
from app.services.quota_guard import QuotaGuard
from app.services.rag_runtime_scope import is_under_path, query_model_fingerprint
from app.services.rate_limiter import SlidingWindowLimiter
from app.services.rbac import can
from app.services.request_context import request_context
from app.services.retry_policy import call_with_retry
from app.services.runtime_metrics import RuntimeMetrics
from app.services.runtime_ops import feature_enabled, resolve_profile_for_request, choose_shadow, append_shadow_run
from app.services.agent_classifier import classify_agent_class
from app.services.consistency_guard import text_similarity
from app.services.retrieval_profiles import normalize_retrieval_profile
from app.services.log_buffer import list_captured_logs
from app.graph.workflow import run_query
from app.agents.synthesis_agent import synthesize_answer

# Import helper functions from utility modules
from app.api.utils.auth_helpers import (
    _require_user,
    _require_user_and_token,
    _require_permission,
    _set_auth_cookie,
    _clear_auth_cookie,
    _enforce_cookie_csrf,
    _resolve_auth_token,
    _auth_cookie_name,
    _auth_cookie_samesite,
    _request_origin,
    _origin_is_allowed,
    _is_valid_admin_approval_token,
    _is_valid_admin_approval_token_for_actor,
)

from app.api.utils.response_helpers import (
    _sse_response,
)

from app.api.utils.query_helpers import (
    _query_limiter_key,
    _is_overload_mode,
    _query_cache_key,
    _trace_id,
    _call_with_supported_kwargs,
    _run_with_query_runtime,
    _user_api_settings_for_runtime,
    _query_model_fingerprint_for_user,
    _normalize_agent_class_hint,
    _normalize_retrieval_strategy,
    _resolve_effective_agent_class,
    _effective_strategy_for_session,
    _launch_shadow_run,
    _maybe_sign_response,
)

from app.api.utils.session_helpers import (
    _history_store_for_user,
    _require_valid_session_id,
    _require_existing_session_for_query,
    _latest_answer_for_same_question,
)

from app.api.utils.memory_helpers import (
    _memory_store_for_user,
    _memory_signals_from_result,
    _build_memory_context_for_session,
    _promote_long_term_memory,
)

from app.api.utils.document_helpers import (
    _is_source_allowed_for_user,
    _is_source_manageable_for_user,
    _list_visible_documents_for_user,
    _allowed_sources_for_user,
    _allowed_sources_for_visible_filenames,
    _source_mtime_ns,
    _visible_index_fingerprint_for_user,
    _vector_context_from_citations,
    _enforce_result_source_scope,
    _source_scope_needs_resynthesis,
    _resynthesize_after_source_scope,
    _list_visible_pdf_names_for_user,
    _visible_doc_chunks_by_filename_for_user,
    _is_file_inventory_question,
    _build_user_file_inventory_answer,
    _guess_agent_class_for_upload,
    _is_probably_valid_upload_signature,
)

from app.api.utils.admin_helpers import (
    _parse_audit_ts,
    _filter_audit_rows,
    _parse_request_ts,
    _extract_grounding_support_from_detail,
    _load_benchmark_queries,
    _check_ollama_ready,
    _check_chroma_ready,
    _runtime_diagnostics_summary,
)

# Global settings and logger
settings = get_settings()
logger = logging.getLogger(__name__)

# Shared service instances
auth_service = AuthDBService()
prompt_store = PromptStore()
auth_scheme = HTTPBearer(auto_error=False)
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


# ============================================================================
# Wrapper functions that need access to global instances
# ============================================================================

# These functions are thin wrappers that inject global dependencies into
# the utility functions, maintaining backward compatibility.

def _query_cache_key_wrapper(
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
    """Wrapper for _query_cache_key that injects dependencies."""
    from app.api.utils.query_helpers import _query_cache_key
    return _query_cache_key(
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
        model_fingerprint_fn=lambda u: _query_model_fingerprint_for_user(u, auth_service, get_global_model_settings),
    )

# Override the imported function with the wrapper
_query_cache_key = _query_cache_key_wrapper


def _run_with_query_runtime_wrapper(*, user: dict[str, Any], request: Request, fn):
    """Wrapper for _run_with_query_runtime that injects dependencies."""
    from app.api.utils.query_helpers import _run_with_query_runtime as _run_impl
    return _run_impl(
        user=user,
        request=request,
        fn=fn,
        query_guard=query_guard,
        runtime_metrics=runtime_metrics,
        api_settings_fn=lambda u: _user_api_settings_for_runtime(u, auth_service),
    )

_run_with_query_runtime = _run_with_query_runtime_wrapper


def _is_overload_mode_wrapper() -> bool:
    """Wrapper for _is_overload_mode that injects dependencies."""
    from app.api.utils.query_helpers import _is_overload_mode as _is_overload_impl
    return _is_overload_impl(query_guard)

_is_overload_mode = _is_overload_mode_wrapper


def _launch_shadow_run_wrapper(*, user: dict[str, Any], session_id: str | None, question: str, primary_result: dict[str, Any]) -> None:
    """Wrapper for _launch_shadow_run that injects dependencies."""
    from app.api.utils.query_helpers import _launch_shadow_run as _launch_impl
    return _launch_impl(
        user=user,
        session_id=session_id,
        question=question,
        primary_result=primary_result,
        shadow_queue=shadow_queue,
    )

_launch_shadow_run = _launch_shadow_run_wrapper


def _effective_strategy_for_session_wrapper(
    *, req_strategy: str | None, user: dict[str, Any], session_id: str | None, question: str
) -> tuple[str, dict[str, Any]]:
    """Wrapper for _effective_strategy_for_session that injects dependencies."""
    from app.api.utils.query_helpers import _effective_strategy_for_session as _effective_impl
    return _effective_impl(
        req_strategy=req_strategy,
        user=user,
        session_id=session_id,
        question=question,
        history_store_fn=_history_store_for_user,
    )

_effective_strategy_for_session = _effective_strategy_for_session_wrapper


def _build_memory_context_for_session_wrapper(user: dict[str, Any], session_id: str | None, question: str) -> str:
    """Wrapper for _build_memory_context_for_session that injects dependencies."""
    from app.api.utils.memory_helpers import _build_memory_context_for_session as _build_impl
    return _build_impl(user, session_id, question, _history_store_for_user)

_build_memory_context_for_session = _build_memory_context_for_session_wrapper


def _enforce_result_source_scope_wrapper(
    result: dict[str, Any], allowed_sources: list[str], request: Request, user: dict[str, Any]
) -> dict[str, Any]:
    """Wrapper for _enforce_result_source_scope that injects dependencies."""
    from app.api.utils.document_helpers import _enforce_result_source_scope as _enforce_impl
    return _enforce_impl(result, allowed_sources, request, user, _audit)

_enforce_result_source_scope = _enforce_result_source_scope_wrapper


def _runtime_diagnostics_summary_wrapper() -> dict[str, Any]:
    """Wrapper for _runtime_diagnostics_summary that injects dependencies."""
    from app.api.middleware import get_request_metrics
    from app.api.utils.admin_helpers import _runtime_diagnostics_summary as _runtime_impl
    return _runtime_impl(get_request_metrics)

_runtime_diagnostics_summary = _runtime_diagnostics_summary_wrapper


def _user_api_settings_for_runtime_wrapper(user: dict[str, Any]) -> dict[str, Any] | None:
    """Wrapper for _user_api_settings_for_runtime that injects dependencies."""
    from app.api.utils.query_helpers import _user_api_settings_for_runtime as _user_api_impl
    return _user_api_impl(user, auth_service)

_user_api_settings_for_runtime = _user_api_settings_for_runtime_wrapper


def _query_model_fingerprint_for_user_wrapper(user: dict[str, Any]) -> str:
    """Wrapper for _query_model_fingerprint_for_user that injects dependencies."""
    from app.api.utils.query_helpers import _query_model_fingerprint_for_user as _query_model_impl
    return _query_model_impl(user, auth_service, get_global_model_settings)

_query_model_fingerprint_for_user = _query_model_fingerprint_for_user_wrapper


# ============================================================================
# Additional helper functions that remain in dependencies.py
# ============================================================================

def _request_meta(request: Request) -> tuple[str | None, str | None]:
    """Get request metadata (IP and user agent)."""
    return request.client.host if request.client else None, request.headers.get("user-agent")


def _client_ip(request: Request) -> str:
    """Get client IP address."""
    ip, _ua = _request_meta(request)
    return ip or "unknown"


def _audit(
    request: Request,
    action: str,
    resource_type: str,
    result: str,
    user: dict[str, Any] | None = None,
    resource_id: str | None = None,
    detail: str | None = None,
) -> None:
    """Log an audit event."""
    ip, user_agent = _request_meta(request)
    auth_service.add_audit_log(
        action=action,
        resource_type=resource_type,
        result=result,
        actor_user_id=user.get("user_id") if user else None,
        actor_role=user.get("role") if user else None,
        resource_id=resource_id,
        ip=ip,
        user_agent=user_agent,
        detail=detail,
    )


def _normalize_prompt_fields(title: str, content: str) -> tuple[str, str]:
    """Normalize and validate prompt fields."""
    t = (title or "").strip()
    c = (content or "").strip()
    if not t:
        raise HTTPException(status_code=400, detail="title is required")
    if not c:
        raise HTTPException(status_code=400, detail="content is required")
    if len(t) > 120:
        raise HTTPException(status_code=400, detail="title too long")
    if len(c) > 6000:
        raise HTTPException(status_code=400, detail="content too long")
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
    return UserApiSettingsView(
        provider=str(settings_data.provider or "").strip().lower() or "ollama",
        api_key_masked=_mask_api_key(settings_data.api_key),
        base_url=str(settings_data.base_url or "").strip(),
        model=str(settings_data.model or "").strip(),
        temperature=float(settings_data.temperature),
        max_tokens=int(settings_data.max_tokens),
    )


def _admin_model_settings_view(settings_data: dict[str, Any]) -> AdminModelSettingsResponse:
    """Convert model settings to admin view model."""
    return AdminModelSettingsResponse(ok=True, settings=public_global_model_settings(settings_data))
