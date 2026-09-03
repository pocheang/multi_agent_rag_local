"""Session management routes for the QueryMind API."""

from typing import Any

from fastapi import APIRouter, Depends, Request

from app.api.dependencies import (
    _allowed_sources_for_user,
    _audit,
    _build_memory_context_for_session,
    _history_store_for_user,
    _memory_store_for_user,
    _promote_long_term_memory,
    _require_permission,
    _require_user,
    _require_valid_session_id,
    _reserve_chat_credit,
)
from app.api.routes.internal.pipeline_contract import execute_standard_compatibility
from app.api.schemas import (
    LongTermMemoryItem,
    MessageUpdateRequest,
    SessionDetail,
    SessionSummary,
)
from app.api.transport.errors import bad_request, not_found
from app.api.transport.middleware import record_grounding_support
from app.pipeline.contracts import PipelineUser
from app.services.query.input_normalizer import (
    enhance_user_question_for_completion,
    normalize_and_validate_user_question,
    normalize_user_question,
)
from app.services.query.intent import is_casual_chat_query
from app.services.security.audit_actions import AuditAction
from app.services.security.rbac import Permission

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.get("", response_model=list[SessionSummary])
def list_sessions(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, Permission.SESSION_READ, request, "session")
    return _history_store_for_user(user).list_sessions()


@router.post("", response_model=SessionDetail)
def create_session(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, Permission.SESSION_CREATE, request, "session")
    session = _history_store_for_user(user).create_session()
    _audit(
        request,
        action=AuditAction.SESSION_CREATE,
        resource_type="session",
        result="success",
        user=user,
        resource_id=session["session_id"],
    )
    return session


@router.get("/{session_id}", response_model=SessionDetail)
def get_session(session_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
    session_id = _require_valid_session_id(session_id)
    _require_permission(user, Permission.SESSION_READ, request, "session", resource_id=session_id)
    data = _history_store_for_user(user).get_session(session_id)
    if data is None:
        raise not_found("Session")
    return data


@router.delete("/{session_id}")
def delete_session(session_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
    session_id = _require_valid_session_id(session_id)
    _require_permission(user, Permission.SESSION_DELETE, request, "session", resource_id=session_id)
    ok = _history_store_for_user(user).delete_session(session_id)
    if not ok:
        raise not_found("Session")
    _audit(
        request,
        action=AuditAction.SESSION_DELETE,
        resource_type="session",
        result="success",
        user=user,
        resource_id=session_id,
    )
    return {"ok": True, "session_id": session_id}


@router.patch("/{session_id}", response_model=SessionDetail)
def update_session(
    session_id: str,
    payload: dict[str, Any],
    request: Request,
    user: dict[str, Any] = Depends(_require_user),
):
    """Update session properties (title, pinned status, etc.)"""
    session_id = _require_valid_session_id(session_id)
    _require_permission(user, Permission.SESSION_UPDATE, request, "session", resource_id=session_id)

    store = _history_store_for_user(user)

    # Check if session exists
    session = store.get_session(session_id)
    if session is None:
        raise not_found("Session")

    # Update title if provided
    if "title" in payload:
        title = str(payload["title"]).strip()
        if not title:
            raise bad_request("Title cannot be empty")
        if len(title) > 200:
            raise bad_request("Title too long (max 200 characters)")

        updated = store.update_session_title(session_id, title)
        if updated is None:
            raise not_found("Session")

        _audit(
            request,
            action=AuditAction.SESSION_RENAME,
            resource_type="session",
            result="success",
            user=user,
            resource_id=session_id,
            detail=f"title={title}",
        )

    # Update pinned status if provided
    if "pinned" in payload:
        pinned = bool(payload["pinned"])
        updated = store.update_session_pinned(session_id, pinned)
        if updated is None:
            raise not_found("Session")

        _audit(
            request,
            action=AuditAction.SESSION_PIN if pinned else "session.unpin",
            resource_type="session",
            result="success",
            user=user,
            resource_id=session_id,
        )

    # Return updated session
    updated_session = store.get_session(session_id)
    if updated_session is None:
        raise not_found("Session")

    return updated_session


@router.get("/{session_id}/memories/long", response_model=list[LongTermMemoryItem])
def list_long_term_memories(session_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
    session_id = _require_valid_session_id(session_id)
    _require_permission(user, Permission.SESSION_READ, request, "session", resource_id=session_id)
    rows = _memory_store_for_user(user).list_long_term(session_id)
    return [LongTermMemoryItem(**x) for x in rows]


@router.delete("/{session_id}/memories/long/{memory_id}")
def delete_long_term_memory(
    session_id: str, memory_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)
):
    session_id = _require_valid_session_id(session_id)
    _require_permission(user, Permission.SESSION_READ, request, "session", resource_id=session_id)
    ok = _memory_store_for_user(user).delete_long_term(session_id=session_id, candidate_id=memory_id)
    if not ok:
        raise not_found("Memory")
    _audit(
        request,
        action=AuditAction.MEMORY_LONG_DELETE,
        resource_type="memory",
        result="success",
        user=user,
        resource_id=memory_id,
    )
    return {"ok": True, "memory_id": memory_id}


@router.patch("/{session_id}/messages/{message_id}", response_model=SessionDetail)
def update_session_message(
    session_id: str,
    message_id: str,
    request: Request,
    req: MessageUpdateRequest,
    rerun: bool = False,
    user: dict[str, Any] = Depends(_require_user),
):
    session_id = _require_valid_session_id(session_id)
    _require_permission(user, Permission.MESSAGE_EDIT, request, "message", resource_id=message_id)
    history_store = _history_store_for_user(user)
    current = history_store.get_message(session_id=session_id, message_id=message_id)
    if current is None:
        raise not_found("Message")

    try:
        if current.get("role") == "user":
            content = normalize_and_validate_user_question(req.content)
        else:
            content = normalize_user_question(req.content)
    except ValueError as e:
        raise bad_request(str(e))

    data = history_store.update_message(session_id=session_id, message_id=message_id, content=content)
    if data is None:
        raise not_found("Message")

    if rerun and current.get("role") == "user":
        effective_question = content if is_casual_chat_query(content) else enhance_user_question_for_completion(content)
        memory_context = _build_memory_context_for_session(
            user=user, session_id=session_id, question=effective_question
        )
        with _reserve_chat_credit(request, user, "message_rerun") as credit:
            result = execute_standard_compatibility(
                question=effective_question,
                use_web_fallback=False,
                use_reasoning=True,
                memory_context=memory_context,
                allowed_sources=_allowed_sources_for_user(user),
                user=PipelineUser(
                    user_id=str(user.get("user_id", "") or "") or None,
                    username=str(user.get("username", "") or "") or None,
                    role=str(user.get("role", "") or "") or None,
                    permissions=frozenset(user.get("permissions") or []),
                ),
                session_id=session_id,
            )
            record_grounding_support(request, result)
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
                    "citations": result.get("vector_result", {}).get("citations", [])
                    + result.get("web_result", {}).get("citations", []),
                },
            )
            if data is None:
                raise not_found("Message")
            _promote_long_term_memory(user=user, session_id=session_id, question=content, result=result)
            credit.commit()
    _audit(
        request,
        action=AuditAction.MESSAGE_UPDATE,
        resource_type="message",
        result="success",
        user=user,
        resource_id=message_id,
    )
    return data


@router.delete("/{session_id}/messages/{message_id}", response_model=SessionDetail)
def delete_session_message(
    session_id: str, message_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)
):
    session_id = _require_valid_session_id(session_id)
    _require_permission(user, Permission.MESSAGE_DELETE, request, "message", resource_id=message_id)
    data = _history_store_for_user(user).delete_message(session_id=session_id, message_id=message_id)
    if data is None:
        raise not_found("Message")
    _audit(
        request,
        action=AuditAction.MESSAGE_DELETE,
        resource_type="message",
        result="success",
        user=user,
        resource_id=message_id,
    )
    return data
