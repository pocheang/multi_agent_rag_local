from pathlib import Path
import logging
import os
import threading
import re
from collections import Counter
from collections import deque
import csv
import hashlib
import hmac
import statistics
import uuid
from datetime import datetime, timedelta, timezone
import io
import socket
import sys
import time
from typing import Annotated, Any
from urllib.parse import urlparse

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
import httpx

from app.core.config import get_settings, reload_settings
from app.core.models import clear_model_caches
from app.ingestion.loaders import IMAGE_EXTENSIONS
from app.core.schemas import (
    AdminRoleUpdateRequest,
    AdminResetPasswordRequest,
    AdminResetApprovalTokenRequest,
    AdminStatusUpdateRequest,
    AdminUserClassificationUpdateRequest,
    AdminCreateAdminRequest,
    AdminUserSummary,
    AuditLogEntry,
    AuthCredentials,
    AuthLoginResponse,
    AuthUser,
    Citation,
    FileIndexActionResponse,
    IndexedFileSummary,
    LongTermMemoryItem,
    MessageUpdateRequest,
    PromptTemplate,
    PromptTemplateCreateRequest,
    PromptCheckRequest,
    PromptCheckResponse,
    PromptTemplateUpdateRequest,
    QueryRequest,
    QueryResponse,
    SessionDetail,
    SessionSummary,
    UploadResponse,
)
from app.graph.streaming import encode_sse, run_query_stream
from app.graph.workflow import run_query
from app.graph.neo4j_client import Neo4jClient
from app.services.auth_db import AuthDBService
from app.services.background_queue import BackgroundTaskQueue
from app.services.alerting import emit_alert, sign_payload, resolve_signing_secret
from app.services.bulkhead import reset_bulkheads
from app.services.history import HistoryStore, validate_session_id
from app.services.memory_store import MemoryStore, build_memory_context
from app.services.ingest_service import ingest_paths
from app.services.index_manager import delete_file_index, list_indexed_files, rebuild_file_index
from app.services.auto_ingest_watcher import AutoIngestWatcher
from app.retrievers.vector_store import clear_vector_store_cache
from app.services.agent_classifier import classify_agent_class
from app.services.input_normalizer import (
    enhance_user_question_for_completion,
    normalize_and_validate_user_question,
    normalize_user_question,
)
from app.services.pdf_agent_guard import (
    apply_pdf_focus_to_question,
    build_choose_pdf_hint,
    build_upload_pdf_hint,
    choose_pdf_targets,
)
from app.services.prompt_store import PromptStore
from app.services.prompt_checker import check_and_enhance_prompt
from app.services.query_intent import is_casual_chat_query, quick_smalltalk_reply
from app.services.query_guard import QueryLoadGuard, QueryOverloadedError, QueryRateLimitedError
from app.services.query_result_cache import QueryResultCache
from app.services.quota_guard import QuotaExceededError, QuotaGuard
from app.services.request_context import overload_mode_enabled, request_context
from app.services.retry_policy import call_with_retry
from app.services.consistency_guard import should_stabilize, text_similarity
from app.services.evidence_conflict import detect_evidence_conflict
from app.services.retrieval_profiles import normalize_retrieval_profile, profile_force_local_only, profile_to_strategy
from app.services.rate_limiter import SlidingWindowLimiter
from app.services.rbac import can
from app.services.runtime_ops import (
    append_index_freshness,
    append_replay_trend,
    append_shadow_run,
    append_benchmark_trend,
    apply_rollback_profile,
    choose_shadow,
    feature_enabled,
    get_runtime_state,
    read_benchmark_trends,
    read_index_freshness,
    read_replay_trends,
    read_shadow_runs,
    resolve_profile_for_request,
    set_active_profile,
    set_canary,
    set_feature_flags,
    set_shadow,
)
from app.services.runtime_metrics import RuntimeMetrics
from app.services.log_buffer import list_captured_logs, setup_log_capture

app = FastAPI(title="Multi-Agent Local RAG")
settings = get_settings()
setup_log_capture()
logger = logging.getLogger(__name__)
if bool(getattr(settings, "cors_enabled", True)):
    cors_origins = settings.cors_origins or []
    allow_all = "*" in cors_origins
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if allow_all else cors_origins,
        allow_credentials=bool(getattr(settings, "cors_allow_credentials", True)) and (not allow_all),
        allow_methods=settings.cors_methods,
        allow_headers=settings.cors_headers,
    )
auth_service = AuthDBService()
prompt_store = PromptStore()
auth_scheme = HTTPBearer(auto_error=False)
auto_ingest_watcher = AutoIngestWatcher(settings=settings)
login_limiter = SlidingWindowLimiter(
    max_attempts=settings.auth_login_max_failures,
    window_seconds=settings.auth_login_window_seconds,
)
register_limiter = SlidingWindowLimiter(
    max_attempts=settings.auth_register_max_attempts,
    window_seconds=settings.auth_register_window_seconds,
)
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
shadow_queue = BackgroundTaskQueue(
    maxsize=settings.shadow_queue_maxsize,
    workers=settings.shadow_queue_workers,
    name="shadow-query",
)
_auto_ingest_stop_event = threading.Event()
_auto_ingest_thread: threading.Thread | None = None
_request_metrics_lock = threading.Lock()
_request_metrics: deque[dict[str, Any]] = deque(maxlen=3000)
runtime_metrics = RuntimeMetrics()

react_dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"
react_index_file = react_dist_dir / "index.html"
react_assets_dir = react_dist_dir / "assets"

# Serve React build assets and fall back SPA routes to index.html.
if react_assets_dir.exists():
    app.mount("/app/assets", StaticFiles(directory=str(react_assets_dir)), name="react-assets")


def _serve_react_index() -> FileResponse:
    if not react_index_file.exists():
        raise HTTPException(status_code=404, detail="frontend build not found")
    return FileResponse(str(react_index_file))


@app.get("/app")
@app.get("/app/")
def serve_react_app_root():
    return _serve_react_index()


@app.get("/app/{frontend_path:path}")
def serve_react_app(frontend_path: str):
    normalized = str(frontend_path or "").strip().strip("/")
    if normalized.startswith("assets/"):
        raise HTTPException(status_code=404, detail="asset not found")
    return _serve_react_index()


@app.middleware("http")
async def request_timing_middleware(request: Request, call_next):
    started = time.perf_counter()
    status_code = 500
    error_text = ""
    trace_id = request.headers.get("x-trace-id", "").strip() or uuid.uuid4().hex
    request.state.trace_id = trace_id
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Trace-Id"] = trace_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        return response
    except Exception as e:
        error_text = type(e).__name__
        raise
    finally:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        metric = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "duration_ms": elapsed_ms,
            "error": error_text,
        }
        with _request_metrics_lock:
            _request_metrics.append(metric)
        runtime_metrics.inc("http_requests_total")
        runtime_metrics.inc(f"http_status_{status_code}_total")
        runtime_metrics.observe("http_request_duration", elapsed_ms / 1000.0)


@app.on_event("startup")
def start_auto_ingest_watcher():
    global _auto_ingest_thread
    logger.info(
        "startup_runtime python=%s conda_env=%s model_backend=%s ollama=%s chat_model=%s",
        sys.executable,
        str(os.environ.get("CONDA_DEFAULT_ENV", "") or ""),
        str(settings.model_backend or ""),
        str(settings.ollama_base_url or ""),
        str(settings.ollama_chat_model or ""),
    )
    shadow_queue.start()
    if not settings.auto_ingest_enabled:
        return
    if _auto_ingest_thread is not None and _auto_ingest_thread.is_alive():
        return
    _auto_ingest_stop_event.clear()
    _auto_ingest_thread = threading.Thread(
        target=auto_ingest_watcher.run_loop,
        args=(lambda: _auto_ingest_stop_event.is_set(),),
        daemon=True,
        name="auto-ingest-watcher",
    )
    _auto_ingest_thread.start()


@app.on_event("shutdown")
def stop_auto_ingest_watcher():
    global _auto_ingest_thread
    _auto_ingest_stop_event.set()
    if _auto_ingest_thread is not None and _auto_ingest_thread.is_alive():
        _auto_ingest_thread.join(timeout=5)
    _auto_ingest_thread = None
    shadow_queue.stop(timeout=2.0)
    Neo4jClient.close_shared_driver()


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
    return QueryResultCache.build_key(
        user_id=str(user.get("user_id", "")),
        session_id=str(session_id or ""),
        question=str(question or ""),
        use_web_fallback=bool(use_web_fallback),
        use_reasoning=bool(use_reasoning),
        retrieval_strategy=str(retrieval_strategy or ""),
        agent_class_hint=str(agent_class_hint or ""),
        request_id=f"{mode}:{str(request_id or '')}",
        include_request_id=False,
    )


def _trace_id(request: Request) -> str:
    return str(getattr(request.state, "trace_id", "") or "").strip() or uuid.uuid4().hex


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
        with query_guard.acquire(limiter_key):
            with request_context(
                timeout_ms=int(getattr(settings, "query_request_timeout_ms", 20000) or 20000),
                overload_mode=_is_overload_mode(),
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
    user_id = str(user.get("user_id", ""))
    items: list[dict[str, Any]] = []
    for row in list_indexed_files():
        source = str(row.get("source", "") or "")
        if not source:
            continue
        source_path = Path(source).resolve()
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


def _enforce_result_source_scope(result: dict[str, Any], allowed_sources: list[str], request: Request, user: dict[str, Any]) -> dict[str, Any]:
    allowed_set = set(allowed_sources)
    if not allowed_set:
        return result
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
    out = dict(result)
    out["vector_result"] = vector_result
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


@app.get("/")
def home():
    return RedirectResponse(url="/app/")


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/metrics")
def metrics():
    guard = query_guard.stats()
    runtime_metrics.set_gauge("query_guard_inflight", float(guard.get("inflight", 0) or 0))
    runtime_metrics.set_gauge("query_guard_waiting", float(guard.get("waiting", 0) or 0))
    qstats = shadow_queue.stats()
    runtime_metrics.set_gauge("shadow_queue_size", float(qstats.get("queue_size", 0) or 0))
    runtime_metrics.set_gauge("shadow_queue_workers", float(qstats.get("workers", 0) or 0))
    return Response(content=runtime_metrics.render_prometheus(), media_type="text/plain; version=0.0.4")


def _check_ollama_ready() -> dict[str, Any]:
    start = time.perf_counter()
    url = (settings.ollama_base_url or "http://localhost:11434").rstrip("/") + "/api/tags"
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
            payload = resp.json()
        models = [str(x.get("name", "") or "") for x in list((payload or {}).get("models", []) or []) if x]
        latency = int((time.perf_counter() - start) * 1000)
        return {
            "ok": True,
            "required": settings.model_backend.lower() == "ollama",
            "latency_ms": latency,
            "path": url,
            "models": models[:8],
        }
    except Exception as e:
        latency = int((time.perf_counter() - start) * 1000)
        return {
            "ok": False,
            "required": settings.model_backend.lower() == "ollama",
            "latency_ms": latency,
            "path": url,
            "error": str(e),
        }


def _check_neo4j_ready() -> dict[str, Any]:
    start = time.perf_counter()
    try:
        parsed = urlparse(settings.neo4j_uri or "")
        host = parsed.hostname or "localhost"
        port = int(parsed.port or 7687)
        with socket.create_connection((host, port), timeout=3):
            pass
        latency = int((time.perf_counter() - start) * 1000)
        return {"ok": True, "required": True, "latency_ms": latency}
    except Exception as e:
        latency = int((time.perf_counter() - start) * 1000)
        return {"ok": False, "required": True, "latency_ms": latency, "error": str(e)}


def _check_chroma_ready() -> dict[str, Any]:
    start = time.perf_counter()
    try:
        settings.chroma_path.mkdir(parents=True, exist_ok=True)
        probe = settings.chroma_path / ".ready_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        latency = int((time.perf_counter() - start) * 1000)
        return {"ok": True, "required": True, "latency_ms": latency, "path": str(settings.chroma_path)}
    except Exception as e:
        latency = int((time.perf_counter() - start) * 1000)
        return {"ok": False, "required": True, "latency_ms": latency, "path": str(settings.chroma_path), "error": str(e)}


def _runtime_diagnostics_summary() -> dict[str, Any]:
    conda_prefix = str(os.environ.get("CONDA_PREFIX", "") or "").strip()
    conda_env = str(os.environ.get("CONDA_DEFAULT_ENV", "") or "").strip()
    recent_errors = list_captured_logs(limit=20, level="ERROR")
    recent_failures = []
    with _request_metrics_lock:
        for row in reversed(list(_request_metrics)):
            status_code = int(row.get("status_code", 0) or 0)
            error = str(row.get("error", "") or "")
            if status_code < 400 and not error:
                continue
            recent_failures.append(
                {
                    "ts": str(row.get("ts", "")),
                    "path": str(row.get("path", "")),
                    "status_code": status_code,
                    "error": error,
                    "duration_ms": int(row.get("duration_ms", 0) or 0),
                }
            )
            if len(recent_failures) >= 10:
                break
    return {
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "conda_prefix": conda_prefix,
        "conda_env": conda_env,
        "model_backend": str(settings.model_backend or ""),
        "reasoning_model_backend": str(settings.reasoning_model_backend or settings.model_backend or ""),
        "ollama_base_url": str(settings.ollama_base_url or ""),
        "ollama_chat_model": str(settings.ollama_chat_model or ""),
        "ollama_embed_model": str(settings.ollama_embed_model or ""),
        "recent_errors": recent_errors[:5],
        "recent_failures": recent_failures,
    }


@app.get("/ready")
def ready():
    checks = {
        "api": {"ok": True, "required": True, "latency_ms": 0},
        "ollama": _check_ollama_ready(),
        "neo4j": _check_neo4j_ready(),
        "chroma": _check_chroma_ready(),
    }
    blocking_failures = [name for name, detail in checks.items() if detail.get("required") and not detail.get("ok")]
    status_text = "ok" if not blocking_failures else "degraded"
    code = 200 if status_text == "ok" else 503
    payload = {
        "status": status_text,
        "blocking_failures": blocking_failures,
        "services": checks,
        "query_runtime": {
            "guard": query_guard.stats(),
            "shadow_queue": shadow_queue.stats(),
        },
    }
    return JSONResponse(content=payload, status_code=code)


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


@app.get("/admin/ops/overview")
def admin_ops_overview(
    request: Request,
    hours: int = 24,
    actor_user_id: str | None = None,
    action_keyword: str | None = None,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:audit_read", request, "admin")
    window_hours = max(1, min(hours, 24 * 7))
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=window_hours)

    audit_rows = auth_service.list_audit_logs(limit=1000)
    window_rows = _filter_audit_rows(
        rows=audit_rows,
        cutoff=cutoff,
        actor_user_id=actor_user_id,
        action_keyword=action_keyword,
    )

    total_requests = len(window_rows)
    error_count = sum(1 for row in window_rows if str(row.get("result", "")).lower() != "success")
    success_count = max(0, total_requests - error_count)
    error_rate = round((error_count / total_requests) * 100, 2) if total_requests > 0 else 0.0

    action_counter = Counter(str(row.get("action", "") or "unknown") for row in window_rows)
    resource_counter = Counter(str(row.get("resource_type", "") or "unknown") for row in window_rows)
    actor_users = {str(row.get("actor_user_id")) for row in window_rows if row.get("actor_user_id")}
    error_reason_counter = Counter(
        str(row.get("detail", "") or str(row.get("action", "") or "unknown_error"))
        for row in window_rows
        if str(row.get("result", "")).lower() != "success"
    )

    users = auth_service.list_users()
    user_total = len(users)
    user_active = sum(1 for row in users if str(row.get("status", "")).lower() == "active")
    user_disabled = user_total - user_active
    user_admin = sum(1 for row in users if str(row.get("role", "")).lower() == "admin")

    active_sessions = auth_service.count_active_sessions()
    login_success = sum(
        1 for row in window_rows if str(row.get("action", "")) == "auth.login" and str(row.get("result", "")).lower() == "success"
    )
    login_failed = sum(
        1 for row in window_rows if str(row.get("action", "")) == "auth.login" and str(row.get("result", "")).lower() != "success"
    )
    query_requests = sum(1 for row in window_rows if str(row.get("action", "")).startswith("query."))
    upload_requests = sum(
        1
        for row in window_rows
        if str(row.get("action", "")) == "document.upload" and str(row.get("result", "")).lower() == "success"
    )

    bucket_counter: dict[str, dict[str, int]] = {}
    for row in window_rows:
        created_at = _parse_audit_ts(str(row.get("created_at", "")))
        bucket = created_at.strftime("%Y-%m-%d %H:00")
        slot = bucket_counter.setdefault(bucket, {"count": 0, "errors": 0})
        slot["count"] += 1
        if str(row.get("result", "")).lower() != "success":
            slot["errors"] += 1
    hourly = [
        {"bucket": key, "count": value["count"], "errors": value["errors"]}
        for key, value in sorted(bucket_counter.items(), key=lambda x: x[0])
    ]

    with _request_metrics_lock:
        req_rows = list(_request_metrics)
    req_window = [r for r in req_rows if _parse_request_ts(str(r.get("ts", ""))) >= cutoff]
    slow_requests = sorted(req_window, key=lambda x: int(x.get("duration_ms", 0)), reverse=True)[:10]
    slow_requests_view = [
        {
            "ts": str(row.get("ts", "")),
            "method": str(row.get("method", "")),
            "path": str(row.get("path", "")),
            "status_code": int(row.get("status_code", 0)),
            "duration_ms": int(row.get("duration_ms", 0)),
            "error": str(row.get("error", "")),
        }
        for row in slow_requests
    ]

    services = {
        "ollama": _check_ollama_ready(),
        "neo4j": _check_neo4j_ready(),
        "chroma": _check_chroma_ready(),
    }
    services_ok = all(bool(x.get("ok")) for x in services.values())

    return {
        "generated_at": now.isoformat(),
        "window_hours": window_hours,
        "status": "healthy" if services_ok else "degraded",
        "kpi": {
            "requests_total": total_requests,
            "requests_success": success_count,
            "requests_error": error_count,
            "error_rate_percent": error_rate,
            "active_users": len(actor_users),
            "active_sessions": active_sessions,
            "queries": query_requests,
            "uploads": upload_requests,
            "login_success": login_success,
            "login_failed": login_failed,
        },
        "users": {
            "total": user_total,
            "active": user_active,
            "disabled": user_disabled,
            "admin": user_admin,
        },
        "top_actions": [{"action": k, "count": v} for k, v in action_counter.most_common(8)],
        "top_resource_types": [{"resource_type": k, "count": v} for k, v in resource_counter.most_common(8)],
        "top_error_reasons": [{"reason": k, "count": v} for k, v in error_reason_counter.most_common(8)],
        "slow_requests": slow_requests_view,
        "hourly": hourly,
        "services": services,
        "diagnostics": _runtime_diagnostics_summary(),
        "filters": {
            "actor_user_id": (actor_user_id or "").strip(),
            "action_keyword": (action_keyword or "").strip(),
        },
    }


@app.get("/admin/ops/export.csv")
def admin_ops_export_csv(
    request: Request,
    hours: int = 24,
    actor_user_id: str | None = None,
    action_keyword: str | None = None,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:audit_read", request, "admin")
    window_hours = max(1, min(hours, 24 * 7))
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=window_hours)

    audit_rows = auth_service.list_audit_logs(limit=1000)
    window_rows = _filter_audit_rows(
        rows=audit_rows,
        cutoff=cutoff,
        actor_user_id=actor_user_id,
        action_keyword=action_keyword,
    )

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["section", "key", "value"])
    writer.writerow(["meta", "generated_at", now.isoformat()])
    writer.writerow(["meta", "window_hours", str(window_hours)])
    writer.writerow(["meta", "actor_user_id", (actor_user_id or "").strip()])
    writer.writerow(["meta", "action_keyword", (action_keyword or "").strip()])
    writer.writerow(["summary", "request_count", str(len(window_rows))])
    writer.writerow([])
    writer.writerow(["audit_created_at", "actor_user_id", "actor_role", "action", "resource_type", "resource_id", "result", "detail"])
    for row in window_rows:
        writer.writerow(
            [
                str(row.get("created_at", "")),
                str(row.get("actor_user_id", "")),
                str(row.get("actor_role", "")),
                str(row.get("action", "")),
                str(row.get("resource_type", "")),
                str(row.get("resource_id", "")),
                str(row.get("result", "")),
                str(row.get("detail", "")),
            ]
        )

    filename = f"ops_report_{now.strftime('%Y%m%d_%H%M%S')}.csv"
    return Response(
        content=out.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.get("/admin/ops/alerts")
def admin_ops_alerts(
    request: Request,
    hours: int = 24,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:audit_read", request, "admin")
    window_hours = max(1, min(hours, 24 * 7))
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(hours=window_hours)

    audit_rows = auth_service.list_audit_logs(limit=2000)
    window_rows = _filter_audit_rows(rows=audit_rows, cutoff=cutoff)
    total = len(window_rows)
    errors = sum(1 for row in window_rows if str(row.get("result", "")).lower() != "success")
    error_rate = (errors / total) * 100 if total > 0 else 0.0

    with _request_metrics_lock:
        req_rows = list(_request_metrics)
    req_window = [r for r in req_rows if _parse_request_ts(str(r.get("ts", ""))) >= cutoff]
    durations = sorted([int(r.get("duration_ms", 0) or 0) for r in req_window])
    p95 = durations[max(0, int(len(durations) * 0.95) - 1)] if durations else 0

    grounding_values = []
    for row in window_rows:
        if str(row.get("action", "")).strip() != "query.run":
            continue
        v = _extract_grounding_support_from_detail(str(row.get("detail", "")))
        if v is not None:
            grounding_values.append(v)
    grounding_avg = (sum(grounding_values) / len(grounding_values)) if grounding_values else 1.0

    alerts = []
    if p95 > int(settings.slo_p95_latency_ms_threshold):
        alerts.append({"type": "latency", "severity": "high", "value": p95, "threshold": int(settings.slo_p95_latency_ms_threshold)})
    if error_rate > float(settings.slo_error_rate_percent_threshold):
        alerts.append(
            {
                "type": "error_rate",
                "severity": "high",
                "value": round(error_rate, 2),
                "threshold": float(settings.slo_error_rate_percent_threshold),
            }
        )
    if grounding_avg < float(settings.slo_grounding_support_ratio_threshold):
        alerts.append(
            {
                "type": "grounding_support",
                "severity": "medium",
                "value": round(grounding_avg, 3),
                "threshold": float(settings.slo_grounding_support_ratio_threshold),
            }
        )

    return {
        "generated_at": now.isoformat(),
        "window_hours": window_hours,
        "status": "alerting" if alerts else "ok",
        "slo": {
            "p95_latency_ms": p95,
            "error_rate_percent": round(error_rate, 2),
            "grounding_support_ratio_avg": round(grounding_avg, 3),
        },
        "alerts": alerts,
    }


@app.get("/admin/ops/retrieval-profile")
def admin_ops_retrieval_profile(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:audit_read", request, "admin")
    state = get_runtime_state()
    return {
        **state,
        "profiles": [
            {"id": "baseline", "label": "Baseline", "desc": "Conservative retrieval, lower risk."},
            {"id": "advanced", "label": "Advanced", "desc": "Default RAGFlow-like advanced strategy."},
            {"id": "safe", "label": "Safe", "desc": "Local-only retrieval, web fallback disabled."},
        ],
    }


@app.post("/admin/ops/retrieval-profile")
def admin_ops_set_retrieval_profile(
    payload: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:ops_manage", request, "admin")
    follow_default = bool(payload.get("follow_config_default", False))
    profile = str(payload.get("profile", "") or "")
    state = set_active_profile(profile=profile or "advanced", follow_config_default=follow_default)
    _audit(
        request,
        action="admin.ops.profile.set",
        resource_type="admin",
        result="success",
        user=user,
        detail=f"profile={state['active_profile']}; follow_default={state['follow_config_default']}",
    )
    return state


@app.post("/admin/ops/canary")
def admin_ops_set_canary(payload: dict[str, Any], request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:ops_manage", request, "admin")
    enabled = bool(payload.get("enabled", False))
    baseline_percent = int(payload.get("baseline_percent", 0) or 0)
    safe_percent = int(payload.get("safe_percent", 0) or 0)
    seed = str(payload.get("seed", "default") or "default")
    state = set_canary(enabled=enabled, baseline_percent=baseline_percent, safe_percent=safe_percent, seed=seed)
    _audit(
        request,
        action="admin.ops.canary.set",
        resource_type="admin",
        result="success",
        user=user,
        detail=f"enabled={enabled}; baseline={baseline_percent}; safe={safe_percent}; seed={seed}",
    )
    return state


@app.post("/admin/ops/feature-flags")
def admin_ops_set_feature_flags(payload: dict[str, Any], request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:ops_manage", request, "admin")
    flags = payload.get("flags", {})
    if not isinstance(flags, dict):
        raise HTTPException(status_code=400, detail="flags must be an object")
    state = set_feature_flags({str(k): str(v) for k, v in flags.items()})
    _audit(
        request,
        action="admin.ops.feature_flags.set",
        resource_type="admin",
        result="success",
        user=user,
        detail=f"flags={len(state.get('feature_flags', {}) or {})}",
    )
    return state


@app.post("/admin/config/reload")
def admin_reload_config(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:ops_manage", request, "admin")
    global settings, query_guard, query_result_cache, quota_guard, shadow_queue
    settings = reload_settings()
    clear_model_caches()
    clear_vector_store_cache()
    Neo4jClient.close_shared_driver()
    reset_bulkheads()
    shadow_queue.stop(timeout=1.0)
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
    shadow_queue = BackgroundTaskQueue(
        maxsize=settings.shadow_queue_maxsize,
        workers=settings.shadow_queue_workers,
        name="shadow-query",
    )
    shadow_queue.start()
    auto_ingest_watcher.settings = settings
    _audit(
        request,
        action="admin.config.reload",
        resource_type="admin",
        result="success",
        user=user,
        detail="settings_reloaded",
    )
    return {
        "ok": True,
        "reloaded_at": datetime.now(timezone.utc).isoformat(),
        "snapshot": {
            "retrieval_profile": settings.retrieval_profile,
            "top_k": settings.top_k,
            "max_context_chunks": settings.max_context_chunks,
            "retrieval_cache_enabled": settings.retrieval_cache_enabled,
            "dynamic_retrieval_enabled": settings.dynamic_retrieval_enabled,
            "query_rewrite_enabled": settings.query_rewrite_enabled,
            "query_decompose_enabled": settings.query_decompose_enabled,
            "rank_feature_enabled": settings.rank_feature_enabled,
        },
    }


@app.post("/admin/ops/rollback")
def admin_ops_rollback(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:ops_manage", request, "admin")
    state = apply_rollback_profile()
    _audit(
        request,
        action="admin.ops.rollback",
        resource_type="admin",
        result="success",
        user=user,
        detail="runtime_profile_rollback_to_baseline",
    )
    return {"ok": True, "state": state}


@app.get("/admin/ops/benchmark/trends")
def admin_ops_benchmark_trends(
    request: Request,
    limit: int = 30,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:audit_read", request, "admin")
    rows = read_benchmark_trends(limit=max(1, min(limit, 300)))
    return {"items": rows, "count": len(rows)}


@app.get("/admin/ops/shadow")
def admin_ops_shadow_get(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:audit_read", request, "admin")
    return get_runtime_state().get("shadow", {})


@app.post("/admin/ops/shadow")
def admin_ops_shadow_set(payload: dict[str, Any], request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:ops_manage", request, "admin")
    state = set_shadow(
        enabled=bool(payload.get("enabled", False)),
        strategy=str(payload.get("strategy", "baseline") or "baseline"),
        sample_percent=int(payload.get("sample_percent", 10) or 10),
        seed=str(payload.get("seed", "shadow") or "shadow"),
    )
    _audit(
        request,
        action="admin.ops.shadow.set",
        resource_type="admin",
        result="success",
        user=user,
        detail=(
            f"enabled={state.get('shadow', {}).get('enabled')}; "
            f"strategy={state.get('shadow', {}).get('strategy')}; "
            f"sample={state.get('shadow', {}).get('sample_percent')}"
        ),
    )
    return state.get("shadow", {})


@app.get("/admin/ops/shadow/runs")
def admin_ops_shadow_runs(request: Request, limit: int = 100, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:audit_read", request, "admin")
    rows = read_shadow_runs(limit=max(1, min(limit, 1000)))
    return {"items": rows, "count": len(rows)}


@app.post("/admin/ops/ab-compare")
def admin_ops_ab_compare(payload: dict[str, Any], request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:ops_manage", request, "admin")
    question = str(payload.get("question", "") or "").strip()
    if not question:
        raise HTTPException(status_code=400, detail="question is required")
    strategies = payload.get("strategies")
    if not isinstance(strategies, list) or not strategies:
        strategies = ["baseline", "advanced", "safe"]
    normalized = [normalize_retrieval_profile(str(x)) for x in strategies]
    runs: dict[str, Any] = {}
    for s in normalized:
        t0 = time.perf_counter()
        res = run_query(question, use_web_fallback=not profile_force_local_only(s), use_reasoning=False, retrieval_strategy=s)
        runs[s] = {
            "latency_ms": round((time.perf_counter() - t0) * 1000.0, 2),
            "answer": str(res.get("answer", "") or ""),
            "grounding_support_ratio": float((res.get("grounding", {}) or {}).get("support_ratio", 0.0) or 0.0),
            "citations": len(res.get("vector_result", {}).get("citations", []) or [])
            + len(res.get("web_result", {}).get("citations", []) or []),
        }
    base = runs.get("advanced") or next(iter(runs.values()))
    diff = {}
    for s, r in runs.items():
        diff[s] = {
            "answer_similarity_vs_advanced": round(text_similarity(str(base.get("answer", "")), str(r.get("answer", ""))), 4),
            "latency_delta_ms_vs_advanced": round(float(r.get("latency_ms", 0.0)) - float(base.get("latency_ms", 0.0)), 2),
            "grounding_delta_vs_advanced": round(
                float(r.get("grounding_support_ratio", 0.0)) - float(base.get("grounding_support_ratio", 0.0)),
                4,
            ),
        }
    return {"question": question, "runs": runs, "diff": diff}


@app.post("/admin/ops/replay-history")
def admin_ops_replay_history(
    payload: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:ops_manage", request, "admin")
    max_questions = max(1, min(int(payload.get("max_questions", 30) or 30), 200))
    strategy = normalize_retrieval_profile(str(payload.get("strategy", "advanced") or "advanced"))
    history_store = _history_store_for_user(user)
    sessions = history_store.list_sessions()
    questions: list[str] = []
    for s in sessions:
        sid = str(s.get("session_id", "") or "")
        if not sid:
            continue
        detail = history_store.get_session(sid) or {}
        for m in detail.get("messages", []) or []:
            if str(m.get("role", "")) == "user":
                q = str(m.get("content", "") or "").strip()
                if q:
                    questions.append(q)
            if len(questions) >= max_questions:
                break
        if len(questions) >= max_questions:
            break
    if not questions:
        raise HTTPException(status_code=400, detail="no historical questions found")

    latencies: list[float] = []
    groundings: list[float] = []
    conflicts = 0
    for q in questions:
        t0 = time.perf_counter()
        res = run_query(q, use_web_fallback=not profile_force_local_only(strategy), use_reasoning=False, retrieval_strategy=strategy)
        latencies.append((time.perf_counter() - t0) * 1000.0)
        groundings.append(float((res.get("grounding", {}) or {}).get("support_ratio", 0.0) or 0.0))
        all_citations = list(res.get("vector_result", {}).get("citations", []) or []) + list(res.get("web_result", {}).get("citations", []) or [])
        if detect_evidence_conflict(all_citations).get("conflict"):
            conflicts += 1
    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "strategy": strategy,
        "num_questions": len(questions),
        "latency_ms": {
            "p50": round(statistics.median(latencies), 2),
            "p95": round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 2),
            "avg": round(statistics.mean(latencies), 2),
        },
        "grounding_support_ratio": {"avg": round(statistics.mean(groundings), 4), "min": round(min(groundings), 4)},
        "conflict_rate": round(conflicts / len(questions), 4),
    }
    append_replay_trend(summary)
    _audit(
        request,
        action="admin.ops.replay.run",
        resource_type="admin",
        result="success",
        user=user,
        detail=f"questions={len(questions)}; strategy={strategy}",
    )
    return {"ok": True, "summary": summary}


@app.get("/admin/ops/replay/trends")
def admin_ops_replay_trends(request: Request, limit: int = 30, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:audit_read", request, "admin")
    rows = read_replay_trends(limit=max(1, min(limit, 300)))
    return {"items": rows, "count": len(rows)}


@app.get("/admin/ops/index-freshness")
def admin_ops_index_freshness(
    request: Request,
    limit: int = 200,
    sla_seconds: int = 120,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:audit_read", request, "admin")
    rows = read_index_freshness(limit=max(1, min(limit, 1000)))
    total = len(rows)
    breached = sum(1 for r in rows if float(r.get("freshness_seconds", 0.0) or 0.0) > float(sla_seconds))
    return {
        "items": rows,
        "count": total,
        "sla_seconds": sla_seconds,
        "breach_count": breached,
        "breach_rate": round((breached / total), 4) if total > 0 else 0.0,
    }


@app.post("/admin/ops/autotune")
def admin_ops_autotune(payload: dict[str, Any], request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:ops_manage", request, "admin")
    target_p95 = float(payload.get("target_p95_ms", 3000) or 3000)
    target_grounding = float(payload.get("target_grounding", 0.65) or 0.65)
    trends = read_replay_trends(limit=1)
    if not trends:
        raise HTTPException(status_code=400, detail="no replay trends found; run replay first")
    latest = trends[-1]
    latest_p95 = float(((latest.get("latency_ms", {}) or {}).get("p95", 0.0) or 0.0))
    latest_grounding = float(((latest.get("grounding_support_ratio", {}) or {}).get("avg", 0.0) or 0.0))
    patch: dict[str, Any] = {}
    if latest_p95 > target_p95:
        patch["TOP_K"] = max(2, int(settings.top_k) - 1)
        patch["MAX_CONTEXT_CHUNKS"] = max(3, int(settings.max_context_chunks) - 1)
    if latest_grounding < target_grounding:
        patch["TOP_K"] = max(int(patch.get("TOP_K", settings.top_k)), int(settings.top_k) + 1)
        patch["RANK_FEATURE_ENABLED"] = True
        patch["DYNAMIC_RETRIEVAL_ENABLED"] = True
    if not patch:
        patch = {"status": "no_change"}
    else:
        if "TOP_K" in patch:
            settings.top_k = int(patch["TOP_K"])
        if "MAX_CONTEXT_CHUNKS" in patch:
            settings.max_context_chunks = int(patch["MAX_CONTEXT_CHUNKS"])
        if "RANK_FEATURE_ENABLED" in patch:
            settings.rank_feature_enabled = bool(patch["RANK_FEATURE_ENABLED"])
        if "DYNAMIC_RETRIEVAL_ENABLED" in patch:
            settings.dynamic_retrieval_enabled = bool(patch["DYNAMIC_RETRIEVAL_ENABLED"])
    _audit(
        request,
        action="admin.ops.autotune",
        resource_type="admin",
        result="success",
        user=user,
        detail=f"patch={patch}",
    )
    return {"ok": True, "latest": latest, "applied_patch": patch}


@app.post("/admin/ops/benchmark/run")
def admin_ops_benchmark_run(
    request: Request,
    max_queries: int = 20,
    strategy: str | None = None,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:ops_manage", request, "admin")
    query_path = Path("data/eval/benchmark_queries.txt")
    queries = _load_benchmark_queries(query_path, limit=max(1, min(max_queries, 100)))
    if not queries:
        raise HTTPException(status_code=400, detail="benchmark query set is empty")

    latencies: list[float] = []
    support_ratios: list[float] = []
    citation_counts: list[int] = []
    used_profile = normalize_retrieval_profile(strategy)
    for q in queries:
        t0 = time.perf_counter()
        result = run_query(
            q,
            use_web_fallback=True,
            use_reasoning=False,
            retrieval_strategy=used_profile,
        )
        latencies.append((time.perf_counter() - t0) * 1000.0)
        support_ratios.append(float((result.get("grounding", {}) or {}).get("support_ratio", 0.0) or 0.0))
        citation_counts.append(
            len(result.get("vector_result", {}).get("citations", []) or [])
            + len(result.get("web_result", {}).get("citations", []) or [])
        )

    entry = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "num_queries": len(queries),
        "strategy": used_profile,
        "latency_ms": {
            "p50": round(statistics.median(latencies), 2),
            "p95": round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 2),
            "avg": round(statistics.mean(latencies), 2),
        },
        "grounding_support_ratio": {
            "avg": round(statistics.mean(support_ratios), 4),
            "min": round(min(support_ratios), 4),
        },
        "citations": {
            "avg": round(statistics.mean(citation_counts), 2),
            "max": max(citation_counts),
        },
    }
    append_benchmark_trend(entry)
    _audit(
        request,
        action="admin.ops.benchmark.run",
        resource_type="admin",
        result="success",
        user=user,
        detail=f"queries={len(queries)}; strategy={used_profile}",
    )
    return {"ok": True, "result": entry}


@app.get("/admin/ops/audit-report.md")
def admin_ops_audit_report_md(
    request: Request,
    hours: int = 24,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:audit_read", request, "admin")
    overview = admin_ops_overview(
        request=request,
        hours=hours,
        actor_user_id=None,
        action_keyword=None,
        user=user,
    )
    alerts = admin_ops_alerts(request=request, hours=hours, user=user)
    lines = [
        "# Ops Audit Report",
        "",
        f"- generated_at: {datetime.now(timezone.utc).isoformat()}",
        f"- window_hours: {hours}",
        f"- status: {overview.get('status', 'unknown')}",
        "",
        "## KPI",
        "",
        f"- requests_total: {overview.get('kpi', {}).get('requests_total', 0)}",
        f"- requests_success: {overview.get('kpi', {}).get('requests_success', 0)}",
        f"- requests_error: {overview.get('kpi', {}).get('requests_error', 0)}",
        f"- error_rate_percent: {overview.get('kpi', {}).get('error_rate_percent', 0)}",
        "",
        "## SLO",
        "",
        f"- p95_latency_ms: {alerts.get('slo', {}).get('p95_latency_ms', 0)}",
        f"- error_rate_percent: {alerts.get('slo', {}).get('error_rate_percent', 0)}",
        f"- grounding_support_ratio_avg: {alerts.get('slo', {}).get('grounding_support_ratio_avg', 0)}",
        "",
        "## Top Actions",
        "",
    ]
    for row in overview.get("top_actions", [])[:10]:
        lines.append(f"- {row.get('action', 'unknown')}: {row.get('count', 0)}")
    lines.extend(["", "## Alerts", ""])
    if not alerts.get("alerts"):
        lines.append("- no_active_alerts")
    else:
        for row in alerts.get("alerts", []):
            lines.append(
                f"- {row.get('type', 'unknown')} ({row.get('severity', 'unknown')}): "
                f"value={row.get('value')} threshold={row.get('threshold')}"
            )
    text = "\n".join(lines) + "\n"
    filename = f"ops_audit_report_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md"
    return Response(
        content=text,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@app.post("/auth/register", response_model=AuthUser)
def register(req: AuthCredentials, request: Request):
    ip = _client_ip(request)
    register_key = f"register::{ip}"
    if register_limiter.is_limited(register_key):
        _audit(request, action="auth.register", resource_type="auth", result="blocked", detail="register_rate_limited")
        raise HTTPException(status_code=429, detail="too many register attempts, retry later")
    try:
        user = auth_service.register(req.username, req.password)
    except ValueError as e:
        register_limiter.record(register_key)
        _audit(request, action="auth.register", resource_type="auth", result="failed", detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    register_limiter.reset(register_key)
    _audit(request, action="auth.register", resource_type="auth", result="success", resource_id=user["user_id"])
    return AuthUser(**user)


@app.post("/auth/login", response_model=AuthLoginResponse)
def login(req: AuthCredentials, request: Request, response: Response):
    ip = _client_ip(request)
    username_key = (req.username or "").strip().lower() or "unknown"
    login_key = f"login::{ip}::{username_key}"
    if login_limiter.is_limited(login_key):
        _audit(request, action="auth.login", resource_type="auth", result="blocked", detail="login_rate_limited")
        raise HTTPException(status_code=429, detail="too many login attempts, retry later")
    try:
        payload = auth_service.login(req.username, req.password)
    except ValueError as e:
        login_limiter.record(login_key)
        _audit(request, action="auth.login", resource_type="auth", result="failed", detail=str(e))
        raise HTTPException(status_code=401, detail=str(e))
    login_limiter.reset(login_key)
    _audit(
        request,
        action="auth.login",
        resource_type="auth",
        result="success",
        resource_id=payload["user"]["user_id"],
        detail=f"user={payload['user']['username']}",
    )
    token_value = str(payload.get("token", "") or "")
    _set_auth_cookie(response, token_value)
    if not bool(getattr(settings, "auth_expose_token_in_response", False)):
        payload = {**payload, "token": ""}
    return AuthLoginResponse(**payload)


@app.post("/auth/logout")
def logout(request: Request, response: Response, auth: tuple[dict[str, Any], str] = Depends(_require_user_and_token)):
    _user, token = auth
    auth_service.logout(token)
    _clear_auth_cookie(response)
    _audit(request, action="auth.logout", resource_type="auth", result="success", user=_user, resource_id=_user["user_id"])
    return {"ok": True}


@app.get("/auth/me", response_model=AuthUser)
def auth_me(user: dict[str, Any] = Depends(_require_user)):
    return AuthUser(**user)


@app.get("/admin/users", response_model=list[AdminUserSummary])
def admin_list_users(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:user_manage", request, "admin")
    rows = auth_service.list_users()
    return [AdminUserSummary(**x) for x in rows]


@app.patch("/admin/users/{user_id}/role", response_model=AdminUserSummary)
def admin_update_user_role(user_id: str, req: AdminRoleUpdateRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:user_manage", request, "admin", resource_id=user_id)
    if str(req.role or "").strip().lower() == "admin":
        raise HTTPException(status_code=400, detail="admin role promotion is restricted; use /admin/users/create-admin")
    try:
        row = auth_service.update_user_role(user_id=user_id, role=req.role)
    except ValueError as e:
        _audit(request, action="admin.user.role_update", resource_type="user", result="failed", user=user, resource_id=user_id, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    if row is None:
        raise HTTPException(status_code=404, detail="user not found")
    _audit(
        request,
        action="admin.user.role_update",
        resource_type="user",
        result="success",
        user=user,
        resource_id=user_id,
        detail=f"role={row['role']}",
    )
    return AdminUserSummary(**row)


@app.post("/admin/users/create-admin", response_model=AdminUserSummary)
def admin_create_user_as_admin(req: AdminCreateAdminRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:user_manage", request, "admin")
    approval_token = req.approval_token or ""
    token_ok, token_mode = _is_valid_admin_approval_token_for_actor(approval_token, str(user.get("user_id", "")))
    if token_mode == "missing":
        raise HTTPException(
            status_code=500,
            detail="approval token is not configured (set ADMIN_CREATE_APPROVAL_TOKEN_HASH or ADMIN_CREATE_APPROVAL_TOKEN)",
        )
    ticket_id = (req.ticket_id or "").strip()
    reason = (req.reason or "").strip()
    new_admin_approval_token = (req.new_admin_approval_token or "").strip()
    if not token_ok:
        _audit(
            request,
            action="admin.user.create_admin",
            resource_type="user",
            result="failed",
            user=user,
            detail=f"approval_failed; mode={token_mode}; ticket={ticket_id or '-'}",
        )
        raise HTTPException(status_code=403, detail="invalid approval token")
    if len(ticket_id) < 3:
        raise HTTPException(status_code=400, detail="ticket_id is required")
    if len(reason) < 5:
        raise HTTPException(status_code=400, detail="reason is required")
    if len(new_admin_approval_token) < 12:
        raise HTTPException(status_code=400, detail="new_admin_approval_token must be at least 12 chars")
    new_admin_approval_hash = hashlib.sha256(new_admin_approval_token.encode("utf-8")).hexdigest()
    try:
        row = auth_service.create_user_with_role(
            username=req.username,
            password=req.password,
            role="admin",
            created_by_user_id=str(user.get("user_id", "")),
            created_by_username=str(user.get("username", "")),
            admin_ticket_id=ticket_id,
            admin_approval_token_hash=new_admin_approval_hash,
        )
    except ValueError as e:
        _audit(
            request,
            action="admin.user.create_admin",
            resource_type="user",
            result="failed",
            user=user,
            detail=str(e),
        )
        raise HTTPException(status_code=400, detail=str(e))
    _audit(
        request,
        action="admin.user.create_admin",
        resource_type="user",
        result="success",
        user=user,
        resource_id=row["user_id"],
        detail=f"username={row['username']}; mode={token_mode}; ticket={ticket_id}; reason={reason}",
    )
    return AdminUserSummary(**row)


@app.post("/admin/users/{user_id}/reset-approval-token", response_model=AdminUserSummary)
def admin_reset_user_approval_token(
    user_id: str,
    req: AdminResetApprovalTokenRequest,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:user_manage", request, "admin", resource_id=user_id)
    target = auth_service.get_user_profile(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="user not found")
    if str(target.get("role", "")).lower() != "admin":
        raise HTTPException(status_code=400, detail="target user is not admin")

    approval_token = req.approval_token or ""
    token_ok, token_mode = _is_valid_admin_approval_token_for_actor(approval_token, str(user.get("user_id", "")))
    if token_mode == "missing":
        raise HTTPException(
            status_code=500,
            detail="approval token is not configured (set ADMIN_CREATE_APPROVAL_TOKEN_HASH or ADMIN_CREATE_APPROVAL_TOKEN)",
        )
    ticket_id = (req.ticket_id or "").strip()
    reason = (req.reason or "").strip()
    new_admin_approval_token = (req.new_admin_approval_token or "").strip()
    if not token_ok:
        _audit(
            request,
            action="admin.user.reset_approval_token",
            resource_type="user",
            result="failed",
            user=user,
            resource_id=user_id,
            detail=f"approval_failed; mode={token_mode}; ticket={ticket_id or '-'}",
        )
        raise HTTPException(status_code=403, detail="invalid approval token")
    if len(ticket_id) < 3:
        raise HTTPException(status_code=400, detail="ticket_id is required")
    if len(reason) < 5:
        raise HTTPException(status_code=400, detail="reason is required")
    if len(new_admin_approval_token) < 12:
        raise HTTPException(status_code=400, detail="new_admin_approval_token must be at least 12 chars")

    token_hash = hashlib.sha256(new_admin_approval_token.encode("utf-8")).hexdigest()
    row = auth_service.update_user_admin_approval_token(
        user_id=user_id,
        admin_approval_token_hash=token_hash,
        admin_ticket_id=ticket_id,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="user not found")

    _audit(
        request,
        action="admin.user.reset_approval_token",
        resource_type="user",
        result="success",
        user=user,
        resource_id=user_id,
        detail=(
            f"target={target.get('username', '-')}; mode={token_mode}; ticket={ticket_id}; reason={reason}; "
            f"actor={user.get('username', '-')}"
        ),
    )
    return AdminUserSummary(**row)


@app.post("/admin/users/{user_id}/reset-password", response_model=AdminUserSummary)
def admin_reset_user_password(
    user_id: str,
    req: AdminResetPasswordRequest,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:user_manage", request, "admin", resource_id=user_id)
    target = auth_service.get_user_profile(user_id)
    if not target:
        raise HTTPException(status_code=404, detail="user not found")

    approval_token = req.approval_token or ""
    token_ok, token_mode = _is_valid_admin_approval_token_for_actor(approval_token, str(user.get("user_id", "")))
    if token_mode == "missing":
        raise HTTPException(
            status_code=500,
            detail="approval token is not configured (set ADMIN_CREATE_APPROVAL_TOKEN_HASH or ADMIN_CREATE_APPROVAL_TOKEN)",
        )
    ticket_id = (req.ticket_id or "").strip()
    reason = (req.reason or "").strip()
    new_password = req.new_password or ""
    if not token_ok:
        _audit(
            request,
            action="admin.user.reset_password",
            resource_type="user",
            result="failed",
            user=user,
            resource_id=user_id,
            detail=f"approval_failed; mode={token_mode}; ticket={ticket_id or '-'}",
        )
        raise HTTPException(status_code=403, detail="invalid approval token")
    if len(ticket_id) < 3:
        raise HTTPException(status_code=400, detail="ticket_id is required")
    if len(reason) < 5:
        raise HTTPException(status_code=400, detail="reason is required")
    try:
        row = auth_service.update_user_password(user_id=user_id, password=new_password)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if row is None:
        raise HTTPException(status_code=404, detail="user not found")

    _audit(
        request,
        action="admin.user.reset_password",
        resource_type="user",
        result="success",
        user=user,
        resource_id=user_id,
        detail=(
            f"target={target.get('username', '-')}; mode={token_mode}; ticket={ticket_id}; reason={reason}; "
            f"actor={user.get('username', '-')}"
        ),
    )
    return AdminUserSummary(**row)


@app.patch("/admin/users/{user_id}/status", response_model=AdminUserSummary)
def admin_update_user_status(user_id: str, req: AdminStatusUpdateRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:user_manage", request, "admin", resource_id=user_id)
    try:
        row = auth_service.update_user_status(user_id=user_id, status=req.status)
    except ValueError as e:
        _audit(request, action="admin.user.status_update", resource_type="user", result="failed", user=user, resource_id=user_id, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))
    if row is None:
        raise HTTPException(status_code=404, detail="user not found")
    _audit(
        request,
        action="admin.user.status_update",
        resource_type="user",
        result="success",
        user=user,
        resource_id=user_id,
        detail=f"status={row['status']}",
    )
    return AdminUserSummary(**row)


@app.patch("/admin/users/{user_id}/classification", response_model=AdminUserSummary)
def admin_update_user_classification(
    user_id: str,
    req: AdminUserClassificationUpdateRequest,
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:user_manage", request, "admin", resource_id=user_id)
    try:
        row = auth_service.update_user_classification(
            user_id=user_id,
            business_unit=req.business_unit,
            department=req.department,
            user_type=req.user_type,
            data_scope=req.data_scope,
        )
    except ValueError as e:
        _audit(
            request,
            action="admin.user.classification_update",
            resource_type="user",
            result="failed",
            user=user,
            resource_id=user_id,
            detail=str(e),
        )
        raise HTTPException(status_code=400, detail=str(e))
    if row is None:
        raise HTTPException(status_code=404, detail="user not found")
    _audit(
        request,
        action="admin.user.classification_update",
        resource_type="user",
        result="success",
        user=user,
        resource_id=user_id,
        detail=(
            f"business_unit={row.get('business_unit') or '-'}; department={row.get('department') or '-'}; "
            f"user_type={row.get('user_type') or '-'}; data_scope={row.get('data_scope') or '-'}"
        ),
    )
    return AdminUserSummary(**row)


@app.get("/admin/audit-logs", response_model=list[AuditLogEntry])
def admin_list_audit_logs(
    request: Request,
    limit: int = 200,
    actor_user_id: str | None = None,
    action_keyword: str | None = None,
    event_category: str | None = None,
    severity: str | None = None,
    result: str | None = None,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:audit_read", request, "admin")
    rows = auth_service.list_audit_logs(
        limit=limit,
        actor_user_id=actor_user_id,
        action_keyword=action_keyword,
        event_category=event_category,
        severity=severity,
        result=result,
    )
    return [AuditLogEntry(**x) for x in rows]


@app.get("/admin/system-logs")
def admin_system_logs(
    request: Request,
    limit: int = 200,
    level: str | None = None,
    logger: str | None = None,
    keyword: str | None = None,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "admin:audit_read", request, "admin")
    rows = list_captured_logs(limit=limit, level=level, logger_keyword=logger, keyword=keyword)
    return {"items": rows, "count": len(rows)}


@app.get("/prompts", response_model=list[PromptTemplate])
def list_prompts(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "prompt:manage", request, "prompt")
    rows = prompt_store.list_prompts(user["user_id"])
    return [PromptTemplate(**x) for x in rows]


@app.post("/prompts", response_model=PromptTemplate)
def create_prompt(req: PromptTemplateCreateRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "prompt:manage", request, "prompt")
    title, content = _normalize_prompt_fields(req.title, req.content)
    agent_class = _resolve_effective_agent_class(f"{title}\n{content}", None)
    row = prompt_store.create_prompt(user_id=user["user_id"], title=title, content=content, agent_class=agent_class)
    _audit(request, action="prompt.create", resource_type="prompt", result="success", user=user, resource_id=row["prompt_id"])
    return PromptTemplate(**row)


@app.post("/prompts/check", response_model=PromptCheckResponse)
def check_prompt(req: PromptCheckRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "prompt:manage", request, "prompt")
    title, content = _normalize_prompt_fields(req.title, req.content)
    checked = check_and_enhance_prompt(title=title, content=content, use_reasoning=req.use_reasoning)
    _audit(request, action="prompt.check", resource_type="prompt", result="success", user=user)
    return PromptCheckResponse(**checked)


@app.patch("/prompts/{prompt_id}", response_model=PromptTemplate)
def update_prompt(prompt_id: str, req: PromptTemplateUpdateRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "prompt:manage", request, "prompt", resource_id=prompt_id)
    title, content = _normalize_prompt_fields(req.title, req.content)
    agent_class = _resolve_effective_agent_class(f"{title}\n{content}", None)
    row = prompt_store.update_prompt(
        user_id=user["user_id"],
        prompt_id=prompt_id,
        title=title,
        content=content,
        agent_class=agent_class,
    )
    if row is None:
        raise HTTPException(status_code=404, detail="prompt not found")
    _audit(request, action="prompt.update", resource_type="prompt", result="success", user=user, resource_id=prompt_id)
    return PromptTemplate(**row)


@app.get("/prompts/{prompt_id}/versions")
def list_prompt_versions(prompt_id: str, request: Request, limit: int = 20, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "prompt:manage", request, "prompt", resource_id=prompt_id)
    rows = prompt_store.list_versions(user_id=user["user_id"], prompt_id=prompt_id, limit=limit)
    return {"items": rows, "count": len(rows)}


@app.post("/prompts/{prompt_id}/versions/{version_id}/approve")
def approve_prompt_version(prompt_id: str, version_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "prompt:manage", request, "prompt", resource_id=prompt_id)
    row = prompt_store.approve_version(
        user_id=user["user_id"],
        prompt_id=prompt_id,
        version_id=version_id,
        approved_by=str(user.get("username", "")),
    )
    if row is None:
        raise HTTPException(status_code=404, detail="prompt version not found")
    _audit(request, action="prompt.version.approve", resource_type="prompt", result="success", user=user, resource_id=prompt_id)
    return row


@app.post("/prompts/{prompt_id}/versions/{version_id}/rollback", response_model=PromptTemplate)
def rollback_prompt_version(prompt_id: str, version_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "prompt:manage", request, "prompt", resource_id=prompt_id)
    row = prompt_store.rollback_to_version(user_id=user["user_id"], prompt_id=prompt_id, version_id=version_id)
    if row is None:
        raise HTTPException(status_code=404, detail="prompt version not found")
    _audit(request, action="prompt.version.rollback", resource_type="prompt", result="success", user=user, resource_id=prompt_id)
    return PromptTemplate(**row)


@app.delete("/prompts/{prompt_id}")
def delete_prompt(prompt_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "prompt:manage", request, "prompt", resource_id=prompt_id)
    ok = prompt_store.delete_prompt(user_id=user["user_id"], prompt_id=prompt_id)
    if not ok:
        raise HTTPException(status_code=404, detail="prompt not found")
    _audit(request, action="prompt.delete", resource_type="prompt", result="success", user=user, resource_id=prompt_id)
    return {"ok": True, "prompt_id": prompt_id}


@app.get("/sessions", response_model=list[SessionSummary])
def list_sessions(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "session:manage", request, "session")
    return _history_store_for_user(user).list_sessions()


@app.post("/sessions", response_model=SessionDetail)
def create_session(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "session:manage", request, "session")
    session = _history_store_for_user(user).create_session()
    _audit(request, action="session.create", resource_type="session", result="success", user=user, resource_id=session["session_id"])
    return session


@app.get("/sessions/{session_id}", response_model=SessionDetail)
def get_session(session_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
    session_id = _require_valid_session_id(session_id)
    _require_permission(user, "session:manage", request, "session", resource_id=session_id)
    data = _history_store_for_user(user).get_session(session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="session not found")
    return data


@app.get("/sessions/{session_id}/strategy-lock")
def get_session_strategy_lock(session_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
    session_id = _require_valid_session_id(session_id)
    _require_permission(user, "session:manage", request, "session", resource_id=session_id)
    store = _history_store_for_user(user)
    data = store.get_session(session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="session not found")
    return {"session_id": session_id, "strategy_lock": store.get_session_strategy_lock(session_id)}


@app.post("/sessions/{session_id}/strategy-lock")
def set_session_strategy_lock(
    session_id: str,
    payload: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    session_id = _require_valid_session_id(session_id)
    _require_permission(user, "session:manage", request, "session", resource_id=session_id)
    strategy_raw = payload.get("strategy_lock")
    strategy = normalize_retrieval_profile(str(strategy_raw)) if strategy_raw else None
    store = _history_store_for_user(user)
    updated = store.set_session_strategy_lock(session_id, strategy)
    if updated is None:
        raise HTTPException(status_code=404, detail="session not found")
    _audit(
        request,
        action="session.strategy_lock.set",
        resource_type="session",
        result="success",
        user=user,
        resource_id=session_id,
        detail=f"strategy_lock={strategy or 'none'}",
    )
    return {"session_id": session_id, "strategy_lock": strategy}


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
    session_id = _require_valid_session_id(session_id)
    _require_permission(user, "session:manage", request, "session", resource_id=session_id)
    ok = _history_store_for_user(user).delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="session not found")
    _audit(request, action="session.delete", resource_type="session", result="success", user=user, resource_id=session_id)
    return {"ok": True, "session_id": session_id}


@app.get("/sessions/{session_id}/memories/long", response_model=list[LongTermMemoryItem])
def list_long_term_memories(session_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
    session_id = _require_valid_session_id(session_id)
    _require_permission(user, "session:manage", request, "session", resource_id=session_id)
    rows = _memory_store_for_user(user).list_long_term(session_id)
    return [LongTermMemoryItem(**x) for x in rows]


@app.delete("/sessions/{session_id}/memories/long/{memory_id}")
def delete_long_term_memory(session_id: str, memory_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
    session_id = _require_valid_session_id(session_id)
    _require_permission(user, "session:manage", request, "session", resource_id=session_id)
    ok = _memory_store_for_user(user).delete_long_term(session_id=session_id, candidate_id=memory_id)
    if not ok:
        raise HTTPException(status_code=404, detail="memory not found")
    _audit(request, action="memory.long.delete", resource_type="memory", result="success", user=user, resource_id=memory_id)
    return {"ok": True, "memory_id": memory_id}


@app.patch("/sessions/{session_id}/messages/{message_id}", response_model=SessionDetail)
def update_session_message(
    session_id: str,
    message_id: str,
    request: Request,
    req: MessageUpdateRequest,
    rerun: bool = False,
    use_web_fallback: bool = False,
    use_reasoning: bool = False,
    user: dict[str, Any] = Depends(_require_user),
):
    session_id = _require_valid_session_id(session_id)
    _require_permission(user, "message:manage", request, "message", resource_id=message_id)
    history_store = _history_store_for_user(user)
    current = history_store.get_message(session_id=session_id, message_id=message_id)
    if current is None:
        raise HTTPException(status_code=404, detail="message not found")

    try:
        if current.get("role") == "user":
            content = normalize_and_validate_user_question(req.content)
        else:
            content = normalize_user_question(req.content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    data = history_store.update_message(session_id=session_id, message_id=message_id, content=content)
    if data is None:
        raise HTTPException(status_code=404, detail="message not found")

    if rerun and current.get("role") == "user":
        effective_question = content if is_casual_chat_query(content) else enhance_user_question_for_completion(content)
        memory_context = _build_memory_context_for_session(user=user, session_id=session_id, question=effective_question)
        result = run_query(
            effective_question,
            use_web_fallback=use_web_fallback,
            use_reasoning=use_reasoning,
            memory_context=memory_context,
            allowed_sources=_allowed_sources_for_user(user),
        )
        data = history_store.upsert_assistant_after_user(
            session_id=session_id,
            user_message_id=message_id,
            assistant_content=result.get("answer", ""),
            metadata={
                "route": result.get("route", "unknown"),
                "agent_class": result.get("agent_class", "general"),
                "web_used": result.get("web_result", {}).get("used", False),
                "thoughts": result.get("thoughts", []),
                "graph_entities": result.get("graph_result", {}).get("entities", []),
                "citations": result.get("vector_result", {}).get("citations", []) + result.get("web_result", {}).get("citations", []),
            },
        )
        if data is None:
            raise HTTPException(status_code=404, detail="message not found")
        _promote_long_term_memory(user=user, session_id=session_id, question=content, result=result)
    _audit(request, action="message.update", resource_type="message", result="success", user=user, resource_id=message_id)
    return data


@app.delete("/sessions/{session_id}/messages/{message_id}", response_model=SessionDetail)
def delete_session_message(session_id: str, message_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
    session_id = _require_valid_session_id(session_id)
    _require_permission(user, "message:manage", request, "message", resource_id=message_id)
    data = _history_store_for_user(user).delete_message(session_id=session_id, message_id=message_id)
    if data is None:
        raise HTTPException(status_code=404, detail="message not found")
    _audit(request, action="message.delete", resource_type="message", result="success", user=user, resource_id=message_id)
    return data


@app.get("/documents", response_model=list[IndexedFileSummary])
def list_documents(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "document:read", request, "document")
    return _list_visible_documents_for_user(user)


@app.delete("/documents/{filename}", response_model=FileIndexActionResponse)
def delete_document(
    filename: str,
    request: Request,
    remove_file: bool = False,
    source: str | None = None,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "document:manage_own", request, "document", resource_id=filename)
    source = source or None
    if source is None:
        raise HTTPException(status_code=400, detail="source is required")
    if not _is_source_manageable_for_user(source, user):
        _audit(request, action="document.delete", resource_type="document", result="denied", user=user, resource_id=filename)
        raise HTTPException(status_code=403, detail="source not allowed")
    try:
        result = FileIndexActionResponse(**delete_file_index(filename, remove_physical_file=remove_file, source=source))
        _audit(request, action="document.delete", resource_type="document", result="success", user=user, resource_id=filename)
        return result
    except ValueError as e:
        _audit(request, action="document.delete", resource_type="document", result="failed", user=user, resource_id=filename, detail=str(e))
        raise HTTPException(status_code=409, detail=str(e))


@app.post("/documents/{filename}/reindex", response_model=FileIndexActionResponse)
def reindex_document(filename: str, request: Request, source: str | None = None, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "document:manage_own", request, "document", resource_id=filename)
    source = source or None
    if source is None:
        raise HTTPException(status_code=400, detail="source is required")
    if not _is_source_manageable_for_user(source, user):
        _audit(request, action="document.reindex", resource_type="document", result="denied", user=user, resource_id=filename)
        raise HTTPException(status_code=403, detail="source not allowed")
    try:
        t0 = time.perf_counter()
        visibility = "private"
        owner_user_id = str(user.get("user_id", ""))
        agent_class = "general"
        for row in list_indexed_files():
            if str(row.get("source", "") or "") == source:
                visibility = str(row.get("visibility", visibility) or visibility)
                owner_user_id = str(row.get("owner_user_id", owner_user_id) or owner_user_id)
                agent_class = str(row.get("agent_class", agent_class) or agent_class)
                break
        metadata_overrides_by_source = {
            source: {
                "owner_user_id": owner_user_id,
                "visibility": visibility,
                "agent_class": agent_class,
            }
        }
        result = FileIndexActionResponse(
            **rebuild_file_index(
                filename,
                source=source,
                metadata_overrides_by_source=metadata_overrides_by_source,
            )
        )
        append_index_freshness(
            {
                "user_id": str(user.get("user_id", "")),
                "filename": filename,
                "source": source,
                "freshness_seconds": round((time.perf_counter() - t0), 4),
                "chunks_indexed": int(result.chunks_indexed or 0),
                "mode": "reindex",
            }
        )
        _audit(request, action="document.reindex", resource_type="document", result="success", user=user, resource_id=filename)
        return result
    except ValueError as e:
        _audit(request, action="document.reindex", resource_type="document", result="failed", user=user, resource_id=filename, detail=str(e))
        raise HTTPException(status_code=409, detail=str(e))
    except FileNotFoundError as e:
        _audit(request, action="document.reindex", resource_type="document", result="failed", user=user, resource_id=filename, detail=str(e))
        raise HTTPException(status_code=404, detail=str(e))


@app.post("/upload", response_model=UploadResponse)
async def upload_files(
    request: Request,
    files: list[UploadFile] = File(...),
    visibility: Annotated[str, Form()] = "private",
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "upload:create", request, "document")
    if len(files) > settings.upload_max_files:
        raise HTTPException(status_code=400, detail=f"too many files, max={settings.upload_max_files}")

    saved_paths: list[Path] = []
    filenames: list[str] = []
    skipped_files: list[str] = []
    requested_visibility = str(visibility or "private").strip().lower()
    if requested_visibility not in {"private", "public"}:
        requested_visibility = "private"
    role = str(user.get("role", "viewer")).lower()
    visibility_applied = requested_visibility if role == "admin" else "private"
    assigned_agent_classes: dict[str, str] = {}
    total_uploaded_bytes = 0
    read_chunk = max(16 * 1024, int(settings.upload_read_chunk_bytes))
    user_upload_root = settings.uploads_path / user["user_id"]
    user_upload_root.mkdir(parents=True, exist_ok=True)

    for f in files:
        if not f.filename:
            continue
        suffix = Path(f.filename).suffix.lower()
        if suffix not in {".txt", ".md", ".pdf", *IMAGE_EXTENSIONS}:
            skipped_files.append(Path(f.filename).name)
            continue
        target = user_upload_root / Path(f.filename).name
        file_uploaded_bytes = 0
        file_head = b""
        try:
            with target.open("wb") as out:
                while True:
                    chunk = await f.read(read_chunk)
                    if not chunk:
                        break
                    if len(file_head) < 16:
                        file_head = (file_head + chunk)[:16]
                    file_uploaded_bytes += len(chunk)
                    total_uploaded_bytes += len(chunk)
                    if file_uploaded_bytes > settings.upload_max_file_bytes:
                        raise HTTPException(status_code=413, detail=f"file too large: {target.name}")
                    if total_uploaded_bytes > settings.upload_max_total_bytes:
                        raise HTTPException(status_code=413, detail="total upload size exceeded")
                    out.write(chunk)
        except HTTPException:
            if target.exists():
                target.unlink()
            raise
        finally:
            await f.close()

        if file_uploaded_bytes <= 0:
            if target.exists():
                target.unlink()
            continue
        if suffix in {".pdf", *IMAGE_EXTENSIONS} and not _is_probably_valid_upload_signature(suffix, file_head):
            if target.exists():
                target.unlink()
            raise HTTPException(status_code=400, detail=f"invalid file signature: {target.name}")
        saved_paths.append(target)
        filenames.append(target.name)
        assigned_agent_classes[str(target)] = _guess_agent_class_for_upload(target.name)

    if not saved_paths:
        detail = "no supported files uploaded"
        if skipped_files:
            detail = f"{detail}; skipped={','.join(skipped_files)}"
        raise HTTPException(status_code=400, detail=detail)

    try:
        for target in saved_paths:
            delete_file_index(target.name, remove_physical_file=False, source=str(target))
    except Exception as e:
        _audit(request, action="document.upload", resource_type="document", result="failed", user=user, detail=f"pre-clean failed: {e}")
        raise HTTPException(status_code=500, detail="upload pre-clean failed")

    ingest_started = time.perf_counter()
    try:
        metadata_overrides_by_source = {
            str(p): {
                "owner_user_id": str(user.get("user_id", "")),
                "visibility": visibility_applied,
                "agent_class": assigned_agent_classes.get(str(p), "general"),
            }
            for p in saved_paths
        }
        result = ingest_paths(
            saved_paths,
            reset_vector_store=False,
            metadata_overrides_by_source=metadata_overrides_by_source,
        )
    except Exception as e:
        _audit(request, action="document.upload", resource_type="document", result="failed", user=user, detail=str(e))
        raise HTTPException(status_code=500, detail="upload ingest failed")
    ingest_elapsed = (time.perf_counter() - ingest_started)
    per_file = ingest_elapsed / max(1, len(saved_paths))
    for p in saved_paths:
        append_index_freshness(
            {
                "user_id": str(user.get("user_id", "")),
                "filename": p.name,
                "source": str(p),
                "freshness_seconds": round(per_file, 4),
                "chunks_indexed": int(result.get("chunks_indexed", 0) or 0),
            }
        )
    _audit(request, action="document.upload", resource_type="document", result="success", user=user, detail=",".join(filenames))
    return UploadResponse(
        filenames=filenames,
        skipped_files=skipped_files,
        visibility_applied=visibility_applied,
        assigned_agent_classes=assigned_agent_classes,
        **result,
    )


@app.post("/query", response_model=QueryResponse)
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

    smalltalk_answer = quick_smalltalk_reply(normalized_question)
    if smalltalk_answer:
        if req.session_id:
            history_store = _history_store_for_user(user)
            history_store.append_message(req.session_id, "user", original_question)
            history_store.append_message(
                req.session_id,
                "assistant",
                smalltalk_answer,
                metadata={
                    "route": "smalltalk_fast",
                    "agent_class": "general",
                    "web_used": False,
                    "graph_entities": [],
                    "citations": [],
                    "reason": "smalltalk_quick_reply",
                },
            )
        return QueryResponse(
            answer=smalltalk_answer,
            route="smalltalk_fast",
            citations=[],
            graph_entities=[],
            web_used=False,
            debug={"reason": "smalltalk_quick_reply", "use_reasoning": False},
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

    is_fast_smalltalk = is_casual_chat_query(normalized_question)
    effective_question = normalized_question if is_fast_smalltalk else enhance_user_question_for_completion(normalized_question)
    memory_context = _build_memory_context_for_session(user=user, session_id=req.session_id, question=effective_question)
    allowed_sources = _allowed_sources_for_user(user)
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
    cached_response = query_result_cache.get(cache_key, session_id=req.session_id)
    if isinstance(cached_response, dict) and cached_response:
        runtime_metrics.inc("query_cache_hit_total")
        return QueryResponse(**cached_response)
    if not query_result_cache.mark_inflight(cache_key):
        runtime_metrics.inc("query_duplicate_total")
        hot_cached = query_result_cache.get(cache_key, session_id=req.session_id)
        if isinstance(hot_cached, dict) and hot_cached:
            return QueryResponse(**hot_cached)
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
        result_local = run_query(effective_question, **runtime_kwargs)
        result_local = _enforce_result_source_scope(result_local, allowed_sources=allowed_sources, request=request, user=user)
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
                    retried = run_query(effective_question, **stabilize_kwargs)
                    retried = _enforce_result_source_scope(retried, allowed_sources=allowed_sources, request=request, user=user)
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
    if req.session_id:
        history_store = _history_store_for_user(user)
        history_store.append_message(req.session_id, "user", original_question)
        history_store.append_message(
            req.session_id,
            "assistant",
            result.get("answer", ""),
            metadata={
                "route": result.get("route", "unknown"),
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


@app.post("/query/stream")
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

        return StreamingResponse(event_gen_file_inventory(), media_type="text/event-stream")

    smalltalk_answer = quick_smalltalk_reply(normalized_question)
    if smalltalk_answer:
        if session_id:
            history_store = _history_store_for_user(user)
            history_store.append_message(session_id, "user", original_question)
            history_store.append_message(
                session_id,
                "assistant",
                smalltalk_answer,
                metadata={
                    "route": "smalltalk_fast",
                    "agent_class": "general",
                    "web_used": False,
                    "graph_entities": [],
                    "citations": [],
                    "reason": "smalltalk_quick_reply",
                },
            )

        def event_gen_smalltalk():
            yield encode_sse({"type": "status", "message": "smalltalk_fast"})
            yield encode_sse({"type": "answer_chunk", "content": smalltalk_answer})
            yield encode_sse(
                {
                    "type": "done",
                    "result": {
                        "answer": smalltalk_answer,
                        "route": "smalltalk_fast",
                        "reason": "smalltalk_quick_reply",
                        "skill": "answer_with_citations",
                        "agent_class": "general",
                        "vector_result": {},
                        "graph_result": {},
                        "web_result": {"used": False, "citations": [], "context": ""},
                        "thoughts": ["检测到闲聊，直接本地快速回复。"],
                    },
                }
            )

        return StreamingResponse(event_gen_smalltalk(), media_type="text/event-stream")

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

            return StreamingResponse(event_gen_pdf_upload_needed(), media_type="text/event-stream")
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

            return StreamingResponse(event_gen_pdf_select_needed(), media_type="text/event-stream")
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

                return StreamingResponse(event_gen_pdf_chunks_zero(), media_type="text/event-stream")
            normalized_question = apply_pdf_focus_to_question(normalized_question, selected_with_chunks)

    is_fast_smalltalk = is_casual_chat_query(normalized_question)
    effective_question = normalized_question if is_fast_smalltalk else enhance_user_question_for_completion(normalized_question)
    history_store = _history_store_for_user(user)
    memory_context = _build_memory_context_for_session(user=user, session_id=session_id, question=effective_question)
    allowed_sources = _allowed_sources_for_user(user)
    normalized_strategy, strategy_meta = _effective_strategy_for_session(
        req_strategy=retrieval_strategy,
        user=user,
        session_id=session_id,
        question=effective_question,
    )
    effective_use_web_fallback = bool(use_web_fallback and (not profile_force_local_only(normalized_strategy)))
    effective_use_reasoning = bool(use_reasoning)
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
    if replay_enabled:
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
            return StreamingResponse(event_gen_replay(), media_type="text/event-stream")

    cached_stream = query_result_cache.get(stream_cache_key, session_id=session_id)
    if isinstance(cached_stream, dict) and cached_stream.get("result"):
        runtime_metrics.inc("query_stream_cache_hit_total")
        done_result = dict(cached_stream.get("result", {}) or {})

        async def event_gen_cached():
            yield encode_sse({"type": "status", "message": "cache_hit"})
            answer_text = str(done_result.get("answer", "") or "")
            if answer_text:
                yield encode_sse({"type": "answer_chunk", "content": answer_text})
            yield encode_sse({"type": "done", "result": done_result})

        return StreamingResponse(event_gen_cached(), media_type="text/event-stream")
    if not query_result_cache.mark_inflight(stream_cache_key):
        runtime_metrics.inc("query_stream_duplicate_total")
        emit_alert(
            "query_stream_duplicate_inflight",
            {"trace_id": _trace_id(request), "session_id": str(session_id or "")},
        )
        raise HTTPException(status_code=409, detail="duplicate request in progress")
    if session_id:
        history_store.append_message(session_id, "user", original_question)

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
                    for event in run_query_stream(
                        effective_question,
                        **runtime_stream_kwargs,
                    ):
                        if await request.is_disconnected():
                            break
                        if event.get("type") == "done":
                            final_result = _enforce_result_source_scope(
                                event.get("result", {}),
                                allowed_sources=allowed_sources,
                                request=request,
                                user=user,
                            )
                            conflict_report = detect_evidence_conflict(
                                list(final_result.get("vector_result", {}).get("citations", []) or [])
                                + list(final_result.get("web_result", {}).get("citations", []) or [])
                            )
                            final_result["evidence_conflict"] = conflict_report
                            if conflict_report.get("conflict"):
                                final_result["answer"] = f"[evidence-conflict-warning]\n{final_result.get('answer', '')}"
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

    return StreamingResponse(event_gen(), media_type="text/event-stream")
