"""
Role-Based Rate Limiting Enhancement

Provides differentiated rate limiting based on user roles.
Admin users get higher quotas than regular users.

Features:
    - Role-aware rate limiting
    - Configurable quotas per role
    - Backward compatible with existing rate limiter
"""

from __future__ import annotations

import threading
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta


def _utcnow() -> datetime:
    return datetime.now(UTC)


class RoleBasedRateLimiter:
    """
    Role-based rate limiter with per-role quotas.

    Example:
        limiter = RoleBasedRateLimiter(
            default_max_attempts=30,
            default_window_seconds=60,
            role_limits={
                "admin": (100, 60),    # 100 requests per minute
                "premium": (60, 60),   # 60 requests per minute
                "user": (30, 60)       # 30 requests per minute (default)
            }
        )

        # Check if limited
        if limiter.is_limited("user123", role="user"):
            raise RateLimitError()

        # Record request
        limiter.record("user123", role="user")
    """

    def __init__(
        self,
        default_max_attempts: int = 30,
        default_window_seconds: int = 60,
        role_limits: dict[str, tuple[int, int]] | None = None,
    ):
        """
        Initialize role-based rate limiter.

        Args:
            default_max_attempts: Default max requests
            default_window_seconds: Default time window (seconds)
            role_limits: Per-role limits {role: (max_attempts, window_seconds)}
        """
        self.default_max_attempts = max(1, int(default_max_attempts))
        self.default_window = timedelta(seconds=max(1, int(default_window_seconds)))

        # Parse role limits
        self.role_limits: dict[str, tuple[int, timedelta]] = {}
        if role_limits:
            for role, (attempts, window_secs) in role_limits.items():
                self.role_limits[role] = (max(1, int(attempts)), timedelta(seconds=max(1, int(window_secs))))

        self._events: dict[str, deque[datetime]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _get_limits(self, role: str | None) -> tuple[int, timedelta]:
        """Get rate limits for a specific role."""
        if role and role in self.role_limits:
            return self.role_limits[role]
        return self.default_max_attempts, self.default_window

    def is_limited(self, key: str, role: str | None = None) -> bool:
        """
        Check if key is rate limited.

        Args:
            key: User identifier
            role: User role (admin, premium, user, etc.)

        Returns:
            True if limited, False otherwise
        """
        if not key:
            return False

        max_attempts, window = self._get_limits(role)
        now = _utcnow()

        with self._lock:
            queue = self._events[key]
            self._trim(queue, now, window)

            if len(queue) >= max_attempts:
                return True
            return False

    def record(self, key: str, role: str | None = None) -> None:
        """
        Record a request.

        Args:
            key: User identifier
            role: User role
        """
        if not key:
            return

        _, window = self._get_limits(role)
        now = _utcnow()

        with self._lock:
            queue = self._events[key]
            self._trim(queue, now, window)
            queue.append(now)

    def reset(self, key: str) -> None:
        """Reset rate limit for a key."""
        if not key:
            return
        with self._lock:
            self._events.pop(key, None)

    def get_remaining(self, key: str, role: str | None = None) -> int:
        """
        Get remaining requests for a key.

        Args:
            key: User identifier
            role: User role

        Returns:
            Number of remaining requests
        """
        if not key:
            return 0

        max_attempts, window = self._get_limits(role)
        now = _utcnow()

        with self._lock:
            queue = self._events[key]
            self._trim(queue, now, window)
            return max(0, max_attempts - len(queue))

    def get_reset_time(self, key: str, role: str | None = None) -> datetime | None:
        """
        Get when rate limit will reset for a key.

        Args:
            key: User identifier
            role: User role

        Returns:
            Reset time or None if not limited
        """
        if not key:
            return None

        _, window = self._get_limits(role)
        now = _utcnow()

        with self._lock:
            queue = self._events[key]
            self._trim(queue, now, window)

            if not queue:
                return None

            # Reset time is when the oldest event expires
            return queue[0] + window

    def _trim(self, queue: deque[datetime], now: datetime, window: timedelta) -> None:
        """Remove expired events from queue."""
        cutoff = now - window
        while queue and queue[0] < cutoff:
            queue.popleft()


# Backward compatibility alias
class SlidingWindowLimiter:
    """
    Legacy sliding window limiter.

    This class is kept for backward compatibility.
    New code should use RoleBasedRateLimiter.
    """

    def __init__(self, max_attempts: int, window_seconds: int):
        self._limiter = RoleBasedRateLimiter(default_max_attempts=max_attempts, default_window_seconds=window_seconds)

    def is_limited(self, key: str) -> bool:
        return self._limiter.is_limited(key)

    def record(self, key: str) -> None:
        self._limiter.record(key)

    def reset(self, key: str) -> None:
        self._limiter.reset(key)
