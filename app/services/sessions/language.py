"""Session language tracking for multilingual response system.

Tracks the last 5 detected languages per session to determine user's language preference.
Uses in-memory storage for MVP implementation.
"""

from collections import Counter

# In-memory storage: {session_id: [list of last 5 detected languages]}
_session_history: dict[str, list[str]] = {}


def update_language_history(session_id: str, detected_language: str) -> None:
    """Update language history for a session (keep last 5).

    Args:
        session_id: The session identifier
        detected_language: The detected language code (e.g., 'zh', 'en')
    """
    if not session_id or not detected_language:
        return

    if session_id not in _session_history:
        _session_history[session_id] = []

    _session_history[session_id].append(detected_language)

    # Keep only last 5
    if len(_session_history[session_id]) > 5:
        _session_history[session_id] = _session_history[session_id][-5:]


def get_language_preference(session_id: str) -> str:
    """Get session language preference (majority language from last 5 queries).

    Args:
        session_id: The session identifier

    Returns:
        The majority language code, or 'zh' as default
    """
    if not session_id:
        return "zh"

    history = _session_history.get(session_id, [])
    if not history:
        return "zh"  # Default to Chinese

    # Return majority language
    counts = Counter(history)
    return counts.most_common(1)[0][0]


def get_language_history(session_id: str) -> list[str]:
    """Get the full language history for a session.

    Args:
        session_id: The session identifier

    Returns:
        List of detected languages (up to last 5)
    """
    return _session_history.get(session_id, []).copy()


def clear_session_history(session_id: str) -> None:
    """Clear language history for a specific session.

    Args:
        session_id: The session identifier
    """
    if session_id in _session_history:
        del _session_history[session_id]


def clear_all_history() -> None:
    """Clear all session language history. Useful for testing."""
    _session_history.clear()
