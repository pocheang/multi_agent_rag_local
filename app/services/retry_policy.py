from __future__ import annotations

import time
from typing import Any, Callable

from app.core.config import get_settings


def _is_retryable(exc: Exception) -> bool:
    text = str(exc or "").lower()
    name = type(exc).__name__.lower()
    non_retry = ("validation", "permission", "forbidden", "unauthorized", "notfound", "keyerror")
    if any(k in name for k in non_retry):
        return False
    if any(k in text for k in ("quota exceeded", "rate limit", "duplicate request", "bad request", "status_code=4")):
        return False
    retry_hints = ("timeout", "temporarily", "connection", "service unavailable", "429", "503", "circuit_open")
    return any(k in text for k in retry_hints) or any(k in name for k in ("timeout", "connection", "httperror"))


def call_with_retry(op_name: str, fn: Callable[[], Any]) -> Any:
    settings = get_settings()
    if not bool(getattr(settings, "query_retry_enabled", True)):
        return fn()
    attempts = max(1, int(getattr(settings, "query_retry_max_attempts", 2) or 2))
    base_delay = max(10, int(getattr(settings, "query_retry_base_delay_ms", 120) or 120))
    last_exc: Exception | None = None
    for i in range(1, attempts + 1):
        try:
            return fn()
        except Exception as e:
            last_exc = e
            if i >= attempts or (not _is_retryable(e)):
                raise
            time.sleep((base_delay * i) / 1000.0)
    if last_exc:
        raise last_exc
    return fn()
