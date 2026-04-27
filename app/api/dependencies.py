"""
Shared dependencies, services, and helper functions for the Multi-Agent Local RAG API.
"""

from pathlib import Path
import hashlib
import inspect
import json
import logging
import re
import threading
import time
import uuid
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Any
from urllib.parse import urlparse

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
from app.services.runtime_ops import feature_enabled
from app.agents.synthesis_agent import synthesize_answer

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
# Helper Functions
# ============================================================================



def _history_store_for_user(user: dict[str, Any]) -> HistoryStore:

    return HistoryStore(base_dir=settings.sessions_path / user["user_id"])





def _require_valid_session_id(session_id: str) -> str:

    try:

        return validate_session_id(session_id)

    except ValueError:

        raise HTTPException(status_code=400, detail="invalid session_id format")





def _require_existing_session_for_query(user: dict[str, Any], session_id: str | None) -> str | None:

    if not session_id:

        return None

    normalized = _require_valid_session_id(session_id)

    if _history_store_for_user(user).get_session(normalized) is None:

        raise HTTPException(status_code=404, detail="session not found")

    return normalized





def _query_limiter_key(user: dict[str, Any], request: Request) -> str:

    user_id = str(user.get("user_id", "") or "").strip()

    if user_id:

        return f"user:{user_id}"

    host = str(getattr(request.client, "host", "") or "").strip()

    return f"ip:{host or 'unknown'}"





def _is_overload_mode() -> bool:

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

) -> str:

    index_fingerprint = _visible_index_fingerprint_for_user(user)

    model_fingerprint = _query_model_fingerprint_for_user(user)

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

    return str(getattr(request.state, "trace_id", "") or "").strip() or uuid.uuid4().hex





def _call_with_supported_kwargs(fn, /, *args, **kwargs):

    try:

        sig = inspect.signature(fn)

    except (TypeError, ValueError):

        return fn(*args, **kwargs)

    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):

        return fn(*args, **kwargs)

    filtered_kwargs = {k: v for k, v in kwargs.items() if k in sig.parameters}

    return fn(*args, **filtered_kwargs)





def _maybe_sign_response(

    payload: dict[str, Any],

    *,

    user: dict[str, Any] | None = None,

    session_id: str = "",

    question: str = "",

) -> tuple[str | None, str | None]:

    if not bool(getattr(settings, "response_signing_enabled", True)):

        return None, None

    uid = str((user or {}).get("user_id", "") or "")

    if not feature_enabled("response_signing", user_id=uid, session_id=session_id, question=question):

        return None, None

    kid, secret = resolve_signing_secret()

    if not secret:

        emit_alert(

            "response_signing_missing_key",

            {

                "feature": "response_signing",

                "user_id": uid,

                "session_id": session_id,

            },

        )

        return None, None

    return sign_payload(payload, secret), kid





def _run_with_query_runtime(

    *,

    user: dict[str, Any],

    request: Request,

    fn,

):

    limiter_key = _query_limiter_key(user, request)

    try:

        api_settings = _user_api_settings_for_runtime(user)

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

                overload_mode=_is_overload_mode(),

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





def _user_api_settings_for_runtime(user: dict[str, Any]) -> dict[str, Any] | None:

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





def _mask_api_key(api_key: str) -> str:

    value = str(api_key or "").strip()

    if not value:

        return ""

    if len(value) <= 8:

        return "*" * len(value)

    return f"{value[:4]}{'*' * (len(value) - 8)}{value[-4:]}"





def _api_settings_view(settings_data: UserApiSettings) -> UserApiSettingsView:

    return UserApiSettingsView(

        provider=str(settings_data.provider or "").strip().lower() or "ollama",

        api_key_masked=_mask_api_key(settings_data.api_key),

        base_url=str(settings_data.base_url or "").strip(),

        model=str(settings_data.model or "").strip(),

        temperature=float(settings_data.temperature),

        max_tokens=int(settings_data.max_tokens),

    )





def _admin_model_settings_view(settings_data: dict[str, Any]) -> AdminModelSettingsResponse:

    return AdminModelSettingsResponse(ok=True, settings=public_global_model_settings(settings_data))





def _memory_store_for_user(user: dict[str, Any]) -> MemoryStore:

    return MemoryStore(base_dir=settings.sessions_path / user["user_id"] / "_long_memory")





def _memory_signals_from_result(result: dict[str, Any]) -> dict[str, Any]:

    vector_result = result.get("vector_result", {}) or {}

    web_result = result.get("web_result", {}) or {}

    vector_citations = vector_result.get("citations", []) or []

    web_citations = web_result.get("citations", []) or []

    return {

        "vector_retrieved": int(vector_result.get("retrieved_count", 0) or 0),

        "vector_effective_hits": int(vector_result.get("effective_hit_count", 0) or 0),

        "citation_count": len(vector_citations) + len(web_citations),

        "web_used": bool(web_result.get("used", False)),

        "route": str(result.get("route", "unknown")),

        "reason": str(result.get("reason", "")),

        "retrieval_diagnostics": vector_result.get("retrieval_diagnostics", {}),

        "grounding": result.get("grounding", {}),

        "explainability": result.get("explainability", {}),

        "answer_safety": result.get("answer_safety", {}),

    }





def _latest_answer_for_same_question(user: dict[str, Any], session_id: str | None, question: str) -> str | None:

    if not session_id:

        return None

    session_data = _history_store_for_user(user).get_session(session_id) or {}

    msgs = list(session_data.get("messages", []) or [])

    if not msgs:

        return None

    target = str(question or "").strip()

    for i in range(len(msgs) - 2, -1, -1):

        m = msgs[i]

        if str(m.get("role", "")) != "user":

            continue

        if str(m.get("content", "")).strip() != target:

            continue

        for j in range(i + 1, len(msgs)):

            n = msgs[j]

            if str(n.get("role", "")) == "assistant":

                return str(n.get("content", "") or "")

        break

    return None





def _build_memory_context_for_session(user: dict[str, Any], session_id: str | None, question: str) -> str:

    if not session_id:

        return ""

    history_store = _history_store_for_user(user)

    session_data = history_store.get_session(session_id) or {}

    messages = session_data.get("messages", []) or []

    long_term = _memory_store_for_user(user).list_long_term(session_id)

    return build_memory_context(question=question, session_messages=messages, long_term_memories=long_term)





def _promote_long_term_memory(user: dict[str, Any], session_id: str | None, question: str, result: dict[str, Any]) -> None:

    if not session_id:

        return

    _memory_store_for_user(user).add_candidate(

        session_id=session_id,

        question=question,

        answer=result.get("answer", ""),

        signals=_memory_signals_from_result(result),

    )





def _is_source_allowed_for_user(source: str | None, user: dict[str, Any]) -> bool:

    if not source:

        return False

    source_path = Path(source).resolve()

    uploads_root = (settings.uploads_path / user["user_id"]).resolve()

    return uploads_root in source_path.parents





def _is_source_manageable_for_user(source: str | None, user: dict[str, Any]) -> bool:

    if not source:

        return False

    role = str(user.get("role", "viewer")).lower()

    source_path = Path(source).resolve()

    if role == "admin":

        uploads_root = settings.uploads_path.resolve()

        return uploads_root in source_path.parents

    uploads_root = (settings.uploads_path / user["user_id"]).resolve()

    return uploads_root in source_path.parents





def _list_visible_documents_for_user(user: dict[str, Any]) -> list[dict[str, Any]]:

    user_upload_root = (settings.uploads_path / user["user_id"]).resolve()

    docs_root = settings.docs_path.resolve()

    user_id = str(user.get("user_id", ""))

    items: list[dict[str, Any]] = []

    for row in list_indexed_files():

        source = str(row.get("source", "") or "")

        if not source:

            continue

        source_path = Path(source).resolve()

        # Treat curated data/docs content as a shared knowledge base.

        if is_under_path(source_path, docs_root):

            items.append(row)

            continue

        owner_user_id = str(row.get("owner_user_id", "") or "")

        visibility = str(row.get("visibility", "private") or "private").lower()

        if visibility == "public":

            items.append(row)

            continue

        if owner_user_id and owner_user_id == user_id:

            items.append(row)

            continue

        # Backward compatibility for legacy records without owner_user_id.

        if user_upload_root in source_path.parents:

            items.append(row)

    return items





def _allowed_sources_for_user(user: dict[str, Any]) -> list[str]:

    allowed: list[str] = []

    for row in _list_visible_documents_for_user(user):

        source = str(row.get("source", "") or "").strip()

        if source and source not in allowed:

            allowed.append(source)

    return allowed





def _allowed_sources_for_visible_filenames(user: dict[str, Any], filenames: list[str]) -> list[str]:

    wanted = {str(x or "").strip() for x in filenames if str(x or "").strip()}

    if not wanted:

        return []

    allowed: list[str] = []

    for row in _list_visible_documents_for_user(user):

        if str(row.get("filename", "") or "") not in wanted:

            continue

        source = str(row.get("source", "") or "").strip()

        if source and source not in allowed:

            allowed.append(source)

    return allowed





def _source_mtime_ns(source: str) -> int:

    try:

        path = Path(source)

        if path.exists() and path.is_file():

            return int(path.stat().st_mtime_ns)

    except Exception:

        return 0

    return 0





def _visible_index_fingerprint_for_user(user: dict[str, Any]) -> str:

    rows = []

    for row in _list_visible_documents_for_user(user):

        source = str(row.get("source", "") or "").strip()

        rows.append(

            {

                "source": source,

                "chunks": int(row.get("chunks", 0) or 0),

                "owner_user_id": str(row.get("owner_user_id", "") or ""),

                "visibility": str(row.get("visibility", "") or ""),

                "agent_class": str(row.get("agent_class", "") or ""),

                "mtime_ns": _source_mtime_ns(source),

            }

        )

    raw = json.dumps(sorted(rows, key=lambda x: x["source"]), ensure_ascii=False, sort_keys=True)

    return hashlib.sha256(raw.encode("utf-8")).hexdigest()





def _query_model_fingerprint_for_user(user: dict[str, Any]) -> str:

    user_id = str(user.get("user_id", "") or "").strip()

    user_api_settings = auth_service.get_user_metadata(user_id, "api_settings") if user_id else None

    return query_model_fingerprint(

        user_api_settings=user_api_settings if isinstance(user_api_settings, dict) else None,

        global_model_settings=get_global_model_settings(),

        app_settings=settings,

    )





def _vector_context_from_citations(citations: list[dict[str, Any]]) -> str:

    blocks = []

    for citation in citations:

        metadata = citation.get("metadata", {}) or {}

        source = str(citation.get("source", "") or Path(str(metadata.get("source", "") or "unknown")).name)

        retrieval_sources = metadata.get("retrieval_sources", [])

        if not isinstance(retrieval_sources, list):

            retrieval_sources = [str(retrieval_sources)]

        retrieval_label = ",".join(str(x) for x in retrieval_sources if str(x).strip()) or "filtered"

        blocks.append(

            f"[SOURCE: {source or 'unknown'}]\n"

            f"[RETRIEVAL: {retrieval_label}]\n"

            f"{str(citation.get('content', '') or '')}"

        )

    return "\n\n".join(blocks)





def _enforce_result_source_scope(result: dict[str, Any], allowed_sources: list[str], request: Request, user: dict[str, Any]) -> dict[str, Any]:

    allowed_set = set(allowed_sources)

    source_scope = dict(result.get("source_scope", {}) or {})

    if not allowed_set:

        vector_result = dict(result.get("vector_result", {}) or {})

        denied = len(list(vector_result.get("citations", []) or []))

        vector_result["citations"] = []

        vector_result["context"] = ""

        vector_result["retrieved_count"] = 0

        vector_result["effective_hit_count"] = 0

        graph_result = dict(result.get("graph_result", {}) or {})

        graph_filtered = bool(

            graph_result.get("context")

            or graph_result.get("entities")

            or graph_result.get("neighbors")

            or graph_result.get("paths")

        )

        if graph_filtered:

            graph_result.update({"context": "", "entities": [], "neighbors": [], "paths": []})

        source_scope.update(

            {

                "checked": True,

                "allowed_source_count": 0,

                "filtered_vector_citations": denied,

                "filtered_graph": graph_filtered,

            }

        )

        out = dict(result)

        out["vector_result"] = vector_result

        out["graph_result"] = graph_result

        out["source_scope"] = source_scope

        _audit(

            request,

            action="query.source_scope",

            resource_type="query",

            result="denied",

            user=user,

            detail=f"no_allowed_sources; filtered_citations={denied}",

        )

        return out

    vector_result = dict(result.get("vector_result", {}) or {})

    citations = list(vector_result.get("citations", []) or [])

    kept = []

    denied = 0

    for c in citations:

        meta = c.get("metadata", {}) or {}

        src = str(meta.get("source", "") or "")

        if src and src in allowed_set:

            kept.append(c)

        else:

            denied += 1

    if denied > 0:

        _audit(

            request,

            action="query.source_scope",

            resource_type="query",

            result="denied",

            user=user,

            detail=f"filtered_citations={denied}",

        )

    else:

        _audit(

            request,

            action="query.source_scope",

            resource_type="query",

            result="success",

            user=user,

            detail=f"citations_checked={len(citations)}",

        )

    vector_result["citations"] = kept

    vector_result["retrieved_count"] = len(kept)

    vector_result["effective_hit_count"] = min(int(vector_result.get("effective_hit_count", len(kept)) or 0), len(kept))

    vector_result["context"] = _vector_context_from_citations(kept)

    source_scope.update(

        {

            "checked": True,

            "allowed_source_count": len(allowed_set),

            "filtered_vector_citations": denied,

            "filtered_graph": False,

        }

    )

    out = dict(result)

    out["vector_result"] = vector_result

    out["source_scope"] = source_scope

    return out





def _source_scope_needs_resynthesis(result: dict[str, Any]) -> bool:

    scope = result.get("source_scope", {}) or {}

    return bool(scope.get("filtered_vector_citations", 0) or scope.get("filtered_graph", False))





def _resynthesize_after_source_scope(

    result: dict[str, Any],

    *,

    question: str,

    memory_context: str,

    use_reasoning: bool,

) -> dict[str, Any]:

    if not _source_scope_needs_resynthesis(result):

        return result

    vector_context = str((result.get("vector_result", {}) or {}).get("context", "") or "")

    graph_context = str((result.get("graph_result", {}) or {}).get("context", "") or "")

    web_context = str((result.get("web_result", {}) or {}).get("context", "") or "")

    answer = synthesize_answer(

        question=question,

        skill_name=str(result.get("skill", "") or "answer_with_citations"),

        memory_context=memory_context,

        vector_context=vector_context,

        graph_context=graph_context,

        web_context=web_context,

        use_reasoning=use_reasoning,

    )

    out = dict(result)

    out["answer"] = answer

    source_scope = dict(out.get("source_scope", {}) or {})

    source_scope["answer_resynthesized"] = True

    out["source_scope"] = source_scope

    return out





def _list_visible_pdf_names_for_user(user: dict[str, Any]) -> list[str]:

    supported = {".pdf", *IMAGE_EXTENSIONS}

    names: list[str] = []

    for row in _list_visible_documents_for_user(user):

        filename = str(row.get("filename", "") or "").strip()

        if Path(filename).suffix.lower() not in supported:

            continue

        if filename not in names:

            names.append(filename)

    return names





def _visible_doc_chunks_by_filename_for_user(user: dict[str, Any]) -> dict[str, int]:

    mapping: dict[str, int] = {}

    for row in _list_visible_documents_for_user(user):

        filename = str(row.get("filename", "") or "").strip()

        if not filename:

            continue

        try:

            chunks = int(row.get("chunks", 0) or 0)

        except Exception:

            chunks = 0

        if filename not in mapping:

            mapping[filename] = chunks

        else:

            mapping[filename] = max(mapping[filename], chunks)

    return mapping





_FILE_INVENTORY_RE = re.compile(r"(几个|多少|数量|有哪些|列表|清单|列出|多少个)")

_FILE_TARGET_RE = re.compile(r"(文件|文档|pdf|资料|上传)")





def _is_file_inventory_question(question: str) -> bool:

    q = (question or "").strip().lower()

    if not q:

        return False

    return bool(_FILE_TARGET_RE.search(q) and _FILE_INVENTORY_RE.search(q))





def _build_user_file_inventory_answer(user: dict[str, Any]) -> str:

    visible = _list_visible_documents_for_user(user)

    total = len(visible)

    if total == 0:

        return "你当前可访问的文件数量为 0。"

    names: list[str] = []

    for row in visible:

        name = str(row.get("filename", "") or "").strip()

        if name and name not in names:

            names.append(name)

    preview = "、".join(names[:20])

    more = ""

    if len(names) > 20:

        more = f"（其余 {len(names) - 20} 个已省略）"

    return f"你当前可访问的文件共 {len(names)} 个：{preview}{more}。"





def _request_meta(request: Request) -> tuple[str | None, str | None]:

    return request.client.host if request.client else None, request.headers.get("user-agent")





def _client_ip(request: Request) -> str:

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





def _require_permission(user: dict[str, Any], action: str, request: Request, resource_type: str, resource_id: str | None = None):

    if can(action, user):

        return

    _audit(request, action=action, resource_type=resource_type, result="denied", user=user, resource_id=resource_id)

    raise HTTPException(status_code=403, detail="forbidden")





def _normalize_prompt_fields(title: str, content: str) -> tuple[str, str]:

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





_ALLOWED_AGENT_CLASSES = {"general", "cybersecurity", "artificial_intelligence", "pdf_text", "policy"}

_ALLOWED_RETRIEVAL_STRATEGIES = {"baseline", "advanced", "safe"}





def _normalize_agent_class_hint(value: str | None) -> str | None:

    hint = str(value or "").strip().lower()

    if hint in _ALLOWED_AGENT_CLASSES:

        return hint

    return None





def _normalize_retrieval_strategy(value: str | None) -> str | None:

    strategy = str(value or "").strip().lower()

    if strategy in _ALLOWED_RETRIEVAL_STRATEGIES:

        return normalize_retrieval_profile(strategy)

    return normalize_retrieval_profile(None)





def _guess_agent_class_for_upload(filename: str) -> str:

    suffix = Path(filename).suffix.lower()

    if suffix in {".pdf", *IMAGE_EXTENSIONS}:

        return "pdf_text"

    guessed = classify_agent_class(Path(filename).stem)

    return guessed if guessed in _ALLOWED_AGENT_CLASSES else "general"





def _is_probably_valid_upload_signature(suffix: str, head: bytes) -> bool:

    prefix = (head or b"")[:16]

    if suffix == ".pdf":

        return prefix.startswith(b"%PDF-")

    if suffix == ".png":

        return prefix.startswith(b"\x89PNG\r\n\x1a\n")

    if suffix in {".jpg", ".jpeg"}:

        return prefix.startswith(b"\xff\xd8\xff")

    if suffix == ".gif":

        return prefix.startswith(b"GIF87a") or prefix.startswith(b"GIF89a")

    if suffix == ".bmp":

        return prefix.startswith(b"BM")

    if suffix in {".tif", ".tiff"}:

        return prefix.startswith(b"II*\x00") or prefix.startswith(b"MM\x00*")

    if suffix == ".webp":

        return len(prefix) >= 12 and prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP"

    return True





def _resolve_effective_agent_class(question: str, agent_class_hint: str | None) -> str:

    hinted = _normalize_agent_class_hint(agent_class_hint)

    if hinted:

        return hinted

    guessed = classify_agent_class(question)

    return guessed if guessed in _ALLOWED_AGENT_CLASSES else "general"





def _auth_cookie_name() -> str:

    value = str(getattr(settings, "auth_cookie_name", "auth_token") or "auth_token").strip()

    return value or "auth_token"





def _auth_cookie_samesite() -> str:

    raw = str(getattr(settings, "auth_cookie_samesite", "lax") or "lax").strip().lower()

    if raw not in {"lax", "strict", "none"}:

        return "lax"

    if raw == "none" and not bool(getattr(settings, "auth_cookie_secure", False)):

        return "lax"

    return raw





def _resolve_auth_token(request: Request, credentials: HTTPAuthorizationCredentials | None) -> tuple[str | None, str | None]:

    if credentials and credentials.credentials:

        token = str(credentials.credentials).strip() or None

        return token, ("bearer" if token else None)

    cookie_value = str(request.cookies.get(_auth_cookie_name(), "") or "").strip()

    token = cookie_value or None

    return token, ("cookie" if token else None)





def _set_auth_cookie(response: Response, token: str) -> None:

    ttl_hours = int(getattr(settings, "auth_token_ttl_hours", 24) or 24)

    max_age = max(300, ttl_hours * 3600)

    response.set_cookie(

        key=_auth_cookie_name(),

        value=token,

        max_age=max_age,

        httponly=True,

        secure=bool(getattr(settings, "auth_cookie_secure", False)),

        samesite=_auth_cookie_samesite(),

        path="/",

    )





def _clear_auth_cookie(response: Response) -> None:

    response.delete_cookie(

        key=_auth_cookie_name(),

        path="/",

    )





def _request_origin(request: Request) -> str | None:

    origin = str(request.headers.get("origin", "") or "").strip()

    if origin:

        return origin

    referer = str(request.headers.get("referer", "") or "").strip()

    if not referer:

        return None

    parsed = urlparse(referer)

    if not parsed.scheme or not parsed.netloc:

        return None

    return f"{parsed.scheme}://{parsed.netloc}"





def _origin_is_allowed(request: Request, origin: str | None) -> bool:

    if not origin:

        return False

    candidate = origin.strip().rstrip("/").lower()

    if not candidate:

        return False

    allowed: set[str] = set()

    for item in settings.cors_origins:

        value = str(item or "").strip().rstrip("/").lower()

        if value:

            allowed.add(value)

    req_origin = str(request.base_url).strip().rstrip("/").lower()

    if req_origin:

        allowed.add(req_origin)

    return candidate in allowed





def _enforce_cookie_csrf(request: Request, token_source: str | None) -> None:

    if token_source != "cookie":

        return

    if request.method.upper() not in {"POST", "PUT", "PATCH", "DELETE"}:

        return

    if _origin_is_allowed(request, _request_origin(request)):

        return

    raise HTTPException(status_code=403, detail="csrf validation failed")





def _require_user(

    request: Request,

    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),

) -> dict[str, Any]:

    token, token_source = _resolve_auth_token(request, credentials)

    if not token:

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")

    _enforce_cookie_csrf(request, token_source)

    user = auth_service.get_user_by_token(token)

    if user is None:

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token")

    auth_service.touch_session(token)

    return user





def _require_user_and_token(

    request: Request,

    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),

) -> tuple[dict[str, Any], str]:

    token, token_source = _resolve_auth_token(request, credentials)

    if not token:

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")

    _enforce_cookie_csrf(request, token_source)

    user = auth_service.get_user_by_token(token)

    if user is None:

        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token")

    auth_service.touch_session(token)

    return user, token






# ============================================================================
# Additional Helper Functions (from later in original main.py)
# ============================================================================

def _parse_audit_ts(value: str | None) -> datetime:
    if not value:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    try:
        dt = datetime.fromisoformat(value)
    except Exception:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _filter_audit_rows(
    rows: list[dict[str, Any]],
    cutoff: datetime,
    actor_user_id: str | None = None,
    action_keyword: str | None = None,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    actor_filter = (actor_user_id or "").strip()
    action_filter = (action_keyword or "").strip().lower()
    for row in rows:
        if _parse_audit_ts(str(row.get("created_at", ""))) < cutoff:
            continue
        if actor_filter and str(row.get("actor_user_id", "") or "") != actor_filter:
            continue
        if action_filter and action_filter not in str(row.get("action", "")).lower():
            continue
        filtered.append(row)
    return filtered


def _parse_request_ts(value: str | None) -> datetime:
    if not value:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    try:
        dt = datetime.fromisoformat(value)
    except Exception:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _extract_grounding_support_from_detail(detail: str | None) -> float | None:
    text = str(detail or "")
    m = re.search(r"grounding_support=([0-9]*\.?[0-9]+)", text)
    if not m:
        return None
    try:
        v = float(m.group(1))
    except Exception:
        return None
    if v < 0:
        return 0.0
    if v > 1:
        return 1.0
    return v


def _load_benchmark_queries(path: Path, limit: int = 100) -> list[str]:
    if not path.exists():
        return []
    rows: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        q = line.strip()
        if q:
            rows.append(q)
    return rows[: max(1, limit)]


def _effective_strategy_for_session(
    *,
    req_strategy: str | None,
    user: dict[str, Any],
    session_id: str | None,
    question: str,
) -> tuple[str, dict[str, Any]]:
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
        lock = _history_store_for_user(user).get_session_strategy_lock(session_id)
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
) -> None:
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


def _is_valid_admin_approval_token(input_token: str) -> tuple[bool, str]:
    token_hash_cfg = (settings.admin_create_approval_token_hash or "").strip().lower()
    token_plain_cfg = (settings.admin_create_approval_token or "").strip()
    token = (input_token or "").strip()

    if token_hash_cfg and token_plain_cfg:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        if hmac.compare_digest(digest, token_hash_cfg):
            return True, "hash"
        return hmac.compare_digest(token, token_plain_cfg), "plain"
    if token_hash_cfg:
        digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
        return hmac.compare_digest(digest, token_hash_cfg), "hash"
    if token_plain_cfg:
        return hmac.compare_digest(token, token_plain_cfg), "plain"
    return False, "missing"


def _is_valid_admin_approval_token_for_actor(input_token: str, actor_user_id: str) -> tuple[bool, str]:
    token = (input_token or "").strip()
    actor = auth_service.get_user_profile(actor_user_id)
    if actor:
        actor_hash = str(actor.get("admin_approval_token_hash", "") or "").strip().lower()
        if actor_hash:
            digest = hashlib.sha256(token.encode("utf-8")).hexdigest()
            if hmac.compare_digest(digest, actor_hash):
                return True, "user_hash"
    return _is_valid_admin_approval_token(token)


def _sse_response(generator: Any) -> StreamingResponse:
    """Create a Server-Sent Events (SSE) streaming response."""
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

