"""
Session-related helper functions for the Multi-Agent Local RAG API.
"""
from typing import Any

from fastapi import HTTPException

from app.core.config import get_settings
from app.services.history import HistoryStore, validate_session_id

settings = get_settings()


def _history_store_for_user(user: dict[str, Any]) -> HistoryStore:
    """Get the history store for a user."""
    return HistoryStore(base_dir=settings.sessions_path / user["user_id"])


def _require_valid_session_id(session_id: str) -> str:
    """Validate and return a session ID."""
    try:
        return validate_session_id(session_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="invalid session_id format")


def _require_existing_session_for_query(user: dict[str, Any], session_id: str | None) -> str | None:
    """Require an existing session for a query."""
    if not session_id:
        return None
    normalized = _require_valid_session_id(session_id)
    if _history_store_for_user(user).get_session(normalized) is None:
        raise HTTPException(status_code=404, detail="session not found")
    return normalized


def _latest_answer_for_same_question(user: dict[str, Any], session_id: str | None, question: str) -> str | None:
    """Get the latest answer for the same question in a session."""
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
