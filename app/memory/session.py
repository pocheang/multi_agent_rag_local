"""Session-memory view over the existing canonical HistoryStore."""

from __future__ import annotations

from typing import Any

from app.services.sessions.history import HistoryStore


class SessionMemory:
    """Read bounded current-session state without creating a second history store."""

    def __init__(self, history: HistoryStore) -> None:
        self._history = history

    def recent_messages(self, session_id: str, *, rounds: int = 3) -> tuple[dict[str, Any], ...]:
        session = self._history.get_session(session_id) or {}
        messages = tuple(session.get("messages", ()) or ())
        return messages[-max(0, rounds) * 2 :] if rounds > 0 else ()


__all__ = ["SessionMemory"]
