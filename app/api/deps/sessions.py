"""
Session-related helper functions for the QueryMind API.
"""

from typing import Any

from app.api.transport.errors import bad_request
from app.core.config import get_settings
from app.services.sessions.history import HistoryStore, validate_session_id

settings = get_settings()


def _history_store_for_user(user: dict[str, Any]) -> HistoryStore:
    """Get the history store for a user."""
    return HistoryStore(base_dir=settings.sessions_path / user["user_id"])


def _require_valid_session_id(session_id: str) -> str:
    """Validate and return a session ID."""
    try:
        return validate_session_id(session_id)
    except ValueError:
        raise bad_request("invalid session_id format")
