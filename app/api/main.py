from pathlib import Path
import threading
import re
from typing import Annotated, Any

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles

from app.core.config import get_settings
from app.ingestion.loaders import IMAGE_EXTENSIONS
from app.core.schemas import (
    AdminRoleUpdateRequest,
    AdminStatusUpdateRequest,
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
from app.services.auth_db import AuthDBService
from app.services.history import HistoryStore
from app.services.memory_store import MemoryStore, build_memory_context
from app.services.ingest_service import ingest_paths
from app.services.index_manager import delete_file_index, list_indexed_files, rebuild_file_index
from app.services.auto_ingest_watcher import AutoIngestWatcher
from app.services.agent_classifier import classify_agent_class
from app.services.input_normalizer import normalize_and_validate_user_question, normalize_user_question
from app.services.pdf_agent_guard import (
    apply_pdf_focus_to_question,
    build_choose_pdf_hint,
    build_upload_pdf_hint,
    choose_pdf_targets,
)
from app.services.prompt_store import PromptStore
from app.services.prompt_checker import check_and_enhance_prompt
from app.services.rate_limiter import SlidingWindowLimiter
from app.services.rbac import can

app = FastAPI(title="Multi-Agent Local RAG")
settings = get_settings()
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
_auto_ingest_stop_event = threading.Event()
_auto_ingest_thread: threading.Thread | None = None

react_dist_dir = Path(__file__).resolve().parents[2] / "frontend" / "dist"

# Mount React frontend
if react_dist_dir.exists():
    app.mount("/app", StaticFiles(directory=str(react_dist_dir), html=True), name="react-app")


@app.on_event("startup")
def start_auto_ingest_watcher():
    global _auto_ingest_thread
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


def _history_store_for_user(user: dict[str, Any]) -> HistoryStore:
    return HistoryStore(base_dir=settings.sessions_path / user["user_id"])


def _memory_store_for_user(user: dict[str, Any]) -> MemoryStore:
    return MemoryStore(base_dir=settings.sessions_path / user["user_id"] / "_long_memory")


def _memory_signals_from_result(result: dict[str, Any]) -> dict[str, Any]:
    vector_result = result.get("vector_result", {}) or {}
    web_result = result.get("web_result", {}) or {}
    vector_citations = vector_result.get("citations", []) or []
    web_citations = web_result.get("citations", []) or []
    return {
        "vector_retrieved": int(vector_result.get("retrieved_count", 0) or 0),
        "citation_count": len(vector_citations) + len(web_citations),
        "web_used": bool(web_result.get("used", False)),
        "route": str(result.get("route", "unknown")),
        "reason": str(result.get("reason", "")),
    }


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


def _require_user(credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme)) -> dict[str, Any]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    user = auth_service.get_user_by_token(credentials.credentials)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token")
    return user


def _require_user_and_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(auth_scheme),
) -> tuple[dict[str, Any], str]:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="authentication required")
    user = auth_service.get_user_by_token(credentials.credentials)
    if user is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid or expired token")
    return user, credentials.credentials


@app.get("/")
def home():
    return RedirectResponse(url="/app/")


@app.get("/health")
def health():
    return {"status": "ok"}


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
def login(req: AuthCredentials, request: Request):
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
    return AuthLoginResponse(**payload)


@app.post("/auth/logout")
def logout(request: Request, auth: tuple[dict[str, Any], str] = Depends(_require_user_and_token)):
    _user, token = auth
    auth_service.logout(token)
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


@app.get("/admin/audit-logs", response_model=list[AuditLogEntry])
def admin_list_audit_logs(request: Request, limit: int = 200, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:audit_read", request, "admin")
    rows = auth_service.list_audit_logs(limit=limit)
    return [AuditLogEntry(**x) for x in rows]


@app.get("/prompts", response_model=list[PromptTemplate])
def list_prompts(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "prompt:manage", request, "prompt")
    rows = prompt_store.list_prompts(user["user_id"])
    return [PromptTemplate(**x) for x in rows]


@app.post("/prompts", response_model=PromptTemplate)
def create_prompt(req: PromptTemplateCreateRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "prompt:manage", request, "prompt")
    title, content = _normalize_prompt_fields(req.title, req.content)
    row = prompt_store.create_prompt(user_id=user["user_id"], title=title, content=content)
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
    row = prompt_store.update_prompt(user_id=user["user_id"], prompt_id=prompt_id, title=title, content=content)
    if row is None:
        raise HTTPException(status_code=404, detail="prompt not found")
    _audit(request, action="prompt.update", resource_type="prompt", result="success", user=user, resource_id=prompt_id)
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
    _require_permission(user, "session:manage", request, "session", resource_id=session_id)
    data = _history_store_for_user(user).get_session(session_id)
    if data is None:
        raise HTTPException(status_code=404, detail="session not found")
    return data


@app.delete("/sessions/{session_id}")
def delete_session(session_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "session:manage", request, "session", resource_id=session_id)
    ok = _history_store_for_user(user).delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="session not found")
    _audit(request, action="session.delete", resource_type="session", result="success", user=user, resource_id=session_id)
    return {"ok": True, "session_id": session_id}


@app.get("/sessions/{session_id}/memories/long", response_model=list[LongTermMemoryItem])
def list_long_term_memories(session_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "session:manage", request, "session", resource_id=session_id)
    rows = _memory_store_for_user(user).list_long_term(session_id)
    return [LongTermMemoryItem(**x) for x in rows]


@app.delete("/sessions/{session_id}/memories/long/{memory_id}")
def delete_long_term_memory(session_id: str, memory_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
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
    use_web_fallback: bool = True,
    use_reasoning: bool = True,
    user: dict[str, Any] = Depends(_require_user),
):
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
        memory_context = _build_memory_context_for_session(user=user, session_id=session_id, question=content)
        result = run_query(
            content,
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
        visibility = "private"
        owner_user_id = str(user.get("user_id", ""))
        for row in list_indexed_files():
            if str(row.get("source", "") or "") == source:
                visibility = str(row.get("visibility", visibility) or visibility)
                owner_user_id = str(row.get("owner_user_id", owner_user_id) or owner_user_id)
                break
        metadata_overrides_by_source = {
            source: {
                "owner_user_id": owner_user_id,
                "visibility": visibility,
            }
        }
        result = FileIndexActionResponse(
            **rebuild_file_index(
                filename,
                source=source,
                metadata_overrides_by_source=metadata_overrides_by_source,
            )
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
        try:
            with target.open("wb") as out:
                while True:
                    chunk = await f.read(read_chunk)
                    if not chunk:
                        break
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
        saved_paths.append(target)
        filenames.append(target.name)

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
        raise HTTPException(status_code=500, detail=f"upload pre-clean failed: {e}")

    try:
        metadata_overrides_by_source = {
            str(p): {
                "owner_user_id": str(user.get("user_id", "")),
                "visibility": visibility_applied,
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
        raise HTTPException(status_code=500, detail=f"upload ingest failed: {e}")
    _audit(request, action="document.upload", resource_type="document", result="success", user=user, detail=",".join(filenames))
    return UploadResponse(
        filenames=filenames,
        skipped_files=skipped_files,
        visibility_applied=visibility_applied,
        **result,
    )


@app.post("/query", response_model=QueryResponse)
def query(req: QueryRequest, request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "query:run", request, "query")
    try:
        normalized_question = normalize_and_validate_user_question(req.question)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    original_question = normalized_question

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

    if classify_agent_class(normalized_question) == "pdf_text":
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

    memory_context = _build_memory_context_for_session(user=user, session_id=req.session_id, question=normalized_question)
    result = run_query(
        normalized_question,
        use_web_fallback=req.use_web_fallback,
        use_reasoning=req.use_reasoning,
        memory_context=memory_context,
        allowed_sources=_allowed_sources_for_user(user),
    )
    vector_citations = [Citation(**x) for x in result.get("vector_result", {}).get("citations", [])]
    web_citations = [Citation(**x) for x in result.get("web_result", {}).get("citations", [])]
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
            },
        )
        _promote_long_term_memory(user=user, session_id=req.session_id, question=original_question, result=result)
    response = QueryResponse(
        answer=result.get("answer", ""),
        route=result.get("route", "unknown"),
        citations=vector_citations + web_citations,
        graph_entities=result.get("graph_result", {}).get("entities", []),
        web_used=result.get("web_result", {}).get("used", False),
        debug={
            "reason": result.get("reason", ""),
            "skill": result.get("skill", ""),
            "agent_class": result.get("agent_class", "general"),
            "vector_retrieved": result.get("vector_result", {}).get("retrieved_count", 0),
            "use_reasoning": req.use_reasoning,
        },
    )
    _audit(request, action="query.run", resource_type="query", result="success", user=user, resource_id=req.session_id or None)
    return response


@app.post("/query/stream")
def stream_query(
    question: Annotated[str, Form(...)],
    request: Request,
    use_web_fallback: Annotated[bool, Form()] = True,
    use_reasoning: Annotated[bool, Form()] = True,
    session_id: Annotated[str | None, Form()] = None,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "query:run", request, "query")
    try:
        normalized_question = normalize_and_validate_user_question(question)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    original_question = normalized_question

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

    if classify_agent_class(normalized_question) == "pdf_text":
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

    history_store = _history_store_for_user(user)
    memory_context = _build_memory_context_for_session(user=user, session_id=session_id, question=normalized_question)
    if session_id:
        history_store.append_message(session_id, "user", original_question)

    def event_gen():
        final_result = None
        for event in run_query_stream(
            normalized_question,
            use_web_fallback=use_web_fallback,
            use_reasoning=use_reasoning,
            memory_context=memory_context,
            allowed_sources=_allowed_sources_for_user(user),
        ):
            if event.get("type") == "done":
                final_result = event.get("result", {})
            yield encode_sse(event)

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
                },
            )
            _promote_long_term_memory(user=user, session_id=session_id, question=original_question, result=final_result)

    return StreamingResponse(event_gen(), media_type="text/event-stream")
