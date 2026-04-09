from __future__ import annotations

import threading

from app.core.config import get_settings
from app.services.rate_limiter import SlidingWindowLimiter


class QuotaExceededError(RuntimeError):
    pass


class QuotaGuard:
    def __init__(self):
        settings = get_settings()
        self._query_limiter = SlidingWindowLimiter(
            max_attempts=max(1, int(getattr(settings, "quota_query_max_per_minute", 120) or 120)),
            window_seconds=60,
        )
        self._web_limiter = SlidingWindowLimiter(
            max_attempts=max(1, int(getattr(settings, "quota_web_max_per_minute", 30) or 30)),
            window_seconds=60,
        )
        self._lock = threading.Lock()
        self._mode = str(getattr(settings, "quota_mode", "user") or "user").strip().lower()

    def _scope_key(self, user: dict) -> str:
        if self._mode == "business_unit":
            bu = str(user.get("business_unit", "") or "").strip().lower()
            if bu:
                return f"bu:{bu}"
        uid = str(user.get("user_id", "") or "").strip()
        return f"user:{uid}"

    def enforce_query_quota(self, user: dict) -> None:
        settings = get_settings()
        if not bool(getattr(settings, "quota_enabled", False)):
            return
        key = self._scope_key(user)
        with self._lock:
            if self._query_limiter.is_limited(key):
                raise QuotaExceededError("query quota exceeded")
            self._query_limiter.record(key)

    def enforce_web_quota(self, user: dict) -> None:
        settings = get_settings()
        if not bool(getattr(settings, "quota_enabled", False)):
            return
        key = f"web:{self._scope_key(user)}"
        with self._lock:
            if self._web_limiter.is_limited(key):
                raise QuotaExceededError("web quota exceeded")
            self._web_limiter.record(key)
