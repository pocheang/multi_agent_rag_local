from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
import threading
from typing import Any, Callable

from app.core.config import get_settings

_LOCK = threading.Lock()
_EXECUTOR: ThreadPoolExecutor | None = None
_MAX_WORKERS: int | None = None
_PENDING = 0
_PENDING_LOCK = threading.Lock()


class HybridExecutorRejectedError(RuntimeError):
    pass


def _resolve_workers() -> int:
    settings = get_settings()
    configured = int(getattr(settings, "hybrid_executor_max_workers", 16) or 16)
    return max(2, configured)


def get_hybrid_executor() -> ThreadPoolExecutor:
    global _EXECUTOR, _MAX_WORKERS
    workers = _resolve_workers()
    with _LOCK:
        if _EXECUTOR is not None and _MAX_WORKERS == workers:
            return _EXECUTOR
        if _EXECUTOR is not None:
            _EXECUTOR.shutdown(wait=False, cancel_futures=True)
        _EXECUTOR = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="hybrid-rag")
        _MAX_WORKERS = workers
        return _EXECUTOR


def submit_hybrid(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Future:
    settings = get_settings()
    max_pending = max(1, int(getattr(settings, "hybrid_executor_max_pending", 256) or 256))
    global _PENDING
    with _PENDING_LOCK:
        if _PENDING >= max_pending:
            raise HybridExecutorRejectedError("hybrid executor queue full")
        _PENDING += 1

    try:
        future = get_hybrid_executor().submit(fn, *args, **kwargs)
    except Exception:
        with _PENDING_LOCK:
            _PENDING = max(0, _PENDING - 1)
        raise

    def _done(_f: Future) -> None:
        global _PENDING
        with _PENDING_LOCK:
            _PENDING = max(0, _PENDING - 1)

    future.add_done_callback(_done)
    return future
