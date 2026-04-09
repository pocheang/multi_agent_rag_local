from __future__ import annotations

from contextlib import contextmanager
import threading
from typing import Iterator

from app.core.config import get_settings
from app.services.runtime_ops import feature_enabled


class BulkheadRejectedError(RuntimeError):
    pass


_LOCK = threading.Lock()
_SEMAPHORES: dict[str, threading.BoundedSemaphore] = {}


def _semaphore(name: str) -> threading.BoundedSemaphore:
    settings = get_settings()
    with _LOCK:
        if name in _SEMAPHORES:
            return _SEMAPHORES[name]
        if name == "llm":
            size = max(1, int(getattr(settings, "bulkhead_llm_max_concurrent", 12) or 12))
        elif name == "neo4j":
            size = max(1, int(getattr(settings, "bulkhead_neo4j_max_concurrent", 20) or 20))
        elif name == "web":
            size = max(1, int(getattr(settings, "bulkhead_web_max_concurrent", 8) or 8))
        else:
            size = 12
        sem = threading.BoundedSemaphore(value=size)
        _SEMAPHORES[name] = sem
        return sem


@contextmanager
def bulkhead(name: str) -> Iterator[None]:
    settings = get_settings()
    if not bool(getattr(settings, "bulkhead_enabled", True)):
        yield
        return
    if not feature_enabled("bulkhead", user_id="", session_id="", question=name):
        yield
        return
    timeout_s = max(1, int(getattr(settings, "bulkhead_acquire_timeout_ms", 1500) or 1500)) / 1000.0
    sem = _semaphore(name)
    ok = sem.acquire(timeout=timeout_s)
    if not ok:
        raise BulkheadRejectedError(f"bulkhead_rejected:{name}")
    try:
        yield
    finally:
        sem.release()


def reset_bulkheads() -> None:
    with _LOCK:
        _SEMAPHORES.clear()
