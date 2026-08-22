"""Language usage analytics service for multilingual response system."""

import logging
import threading
from collections import Counter
from datetime import UTC, datetime
from typing import Any

logger = logging.getLogger(__name__)


class LanguageAnalytics:
    """
    In-memory language usage analytics logger.

    Tracks language detection events for system-wide usage statistics.
    Thread-safe singleton implementation.
    """

    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        """Initialize analytics storage."""
        self._events: list[dict[str, Any]] = []
        self._events_lock = threading.Lock()

    @classmethod
    def get_instance(cls) -> "LanguageAnalytics":
        """Get singleton instance (thread-safe)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def log_detection(
        self,
        query: str,
        detected_language: str,
        force_language: str = "",
        session_id: str = "",
    ) -> None:
        """
        Log a language detection event.

        Args:
            query: User query text
            detected_language: Detected language code ('zh' or 'en')
            force_language: Forced language code if overridden (empty string if auto-detected)
            session_id: Session identifier
        """
        event = {
            "timestamp": datetime.now(UTC).isoformat(),
            "query": query[:100],  # Truncate for privacy/storage
            "detected_language": detected_language,
            "force_language": force_language,
            "was_forced": bool(force_language),
            "session_id": session_id,
        }

        with self._events_lock:
            self._events.append(event)
            # Keep only last 10,000 events to prevent unbounded memory growth
            if len(self._events) > 10000:
                self._events = self._events[-10000:]

        logger.debug(
            f"Logged language detection: {detected_language} (forced={bool(force_language)}, session={session_id})"
        )

    def get_statistics(self) -> dict[str, Any]:
        """
        Get language usage statistics.

        Returns:
            dict with statistics including:
                - total_queries: Total number of queries logged
                - language_distribution: Count by language
                - forced_vs_auto: Count of forced vs auto-detected
                - recent_events: Last 100 events
        """
        with self._events_lock:
            events = list(self._events)  # Copy for thread safety

        if not events:
            return {
                "total_queries": 0,
                "language_distribution": {},
                "forced_vs_auto": {"auto_detected": 0, "forced": 0},
                "session_count": 0,
                "recent_events": [],
            }

        # Calculate statistics
        language_counter = Counter(e["detected_language"] for e in events)
        forced_count = sum(1 for e in events if e["was_forced"])
        auto_count = len(events) - forced_count
        unique_sessions = len(set(e["session_id"] for e in events if e["session_id"]))

        # Get recent events (last 100, most recent first)
        recent = events[-100:][::-1]

        return {
            "total_queries": len(events),
            "language_distribution": dict(language_counter),
            "forced_vs_auto": {
                "auto_detected": auto_count,
                "forced": forced_count,
            },
            "session_count": unique_sessions,
            "recent_events": recent,
        }

    def get_session_statistics(self, session_id: str) -> dict[str, Any]:
        """
        Get language usage statistics for a specific session.

        Args:
            session_id: Session identifier

        Returns:
            dict with session-specific statistics
        """
        with self._events_lock:
            session_events = [e for e in self._events if e["session_id"] == session_id]

        if not session_events:
            return {
                "session_id": session_id,
                "total_queries": 0,
                "language_distribution": {},
                "forced_vs_auto": {"auto_detected": 0, "forced": 0},
                "events": [],
            }

        language_counter = Counter(e["detected_language"] for e in session_events)
        forced_count = sum(1 for e in session_events if e["was_forced"])
        auto_count = len(session_events) - forced_count

        return {
            "session_id": session_id,
            "total_queries": len(session_events),
            "language_distribution": dict(language_counter),
            "forced_vs_auto": {
                "auto_detected": auto_count,
                "forced": forced_count,
            },
            "events": session_events[::-1],  # Most recent first
        }

    def clear_statistics(self) -> None:
        """Clear all stored analytics (admin operation)."""
        with self._events_lock:
            self._events.clear()
        logger.info("Language analytics cleared")
