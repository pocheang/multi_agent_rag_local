from __future__ import annotations

from contextlib import contextmanager
import threading
import time
from typing import Iterator

from app.core.config import get_settings
from app.services.rate_limiter import SlidingWindowLimiter


class QueryRateLimitedError(RuntimeError):
    pass


class QueryOverloadedError(RuntimeError):
    pass


_REDIS_CLIENT = None
_REDIS_LOCK = threading.Lock()


def _get_redis_client():
    global _REDIS_CLIENT
    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT
    with _REDIS_LOCK:
        if _REDIS_CLIENT is not None:
            return _REDIS_CLIENT
        settings = get_settings()
        try:
            import redis  # type: ignore

            _REDIS_CLIENT = redis.from_url(str(getattr(settings, "redis_url", "")), decode_responses=True)
            _REDIS_CLIENT.ping()
            return _REDIS_CLIENT
        except Exception:
            _REDIS_CLIENT = None
            return None


class QueryLoadGuard:
    def __init__(
        self,
        *,
        per_user_max_requests: int,
        per_user_window_seconds: int,
        max_concurrent: int,
        max_waiting: int,
        acquire_timeout_ms: int,
        backend: str = "auto",
    ):
        self._user_limiter = SlidingWindowLimiter(
            max_attempts=max(1, int(per_user_max_requests)),
            window_seconds=max(1, int(per_user_window_seconds)),
        )
        self._semaphore = threading.BoundedSemaphore(value=max(1, int(max_concurrent)))
        self._max_waiting = max(0, int(max_waiting))
        self._acquire_timeout_s = max(1, int(acquire_timeout_ms)) / 1000.0
        self._state_lock = threading.Lock()
        self._waiting = 0
        self._inflight = 0
        self._max_concurrent = max(1, int(max_concurrent))
        self._max_per_user = max(1, int(per_user_max_requests))
        self._window_seconds = max(1, int(per_user_window_seconds))
        b = str(backend or "auto").strip().lower()
        if b not in {"auto", "memory", "redis"}:
            b = "auto"
        self._backend = b

    def _effective_backend(self) -> str:
        if self._backend == "memory":
            return "memory"
        if self._backend == "redis":
            return "redis" if _get_redis_client() is not None else "memory"
        return "redis" if _get_redis_client() is not None else "memory"

    def stats(self) -> dict[str, int | str]:
        if self._effective_backend() == "redis":
            client = _get_redis_client()
            inflight = 0
            waiting = 0
            if client is not None:
                try:
                    inflight = int(client.get("qguard:inflight") or 0)
                    waiting = int(client.get("qguard:waiting") or 0)
                except Exception:
                    inflight = 0
                    waiting = 0
            return {
                "backend": "redis",
                "inflight": inflight,
                "waiting": waiting,
                "max_concurrent": self._max_concurrent,
                "max_waiting": self._max_waiting,
            }
        with self._state_lock:
            return {
                "backend": "memory",
                "inflight": self._inflight,
                "waiting": self._waiting,
                "max_concurrent": self._max_concurrent,
                "max_waiting": self._max_waiting,
            }

    @contextmanager
    def acquire(self, user_key: str) -> Iterator[dict[str, int | str]]:
        if self._effective_backend() == "redis":
            with self._acquire_redis(user_key):
                yield self.stats()
            return
        with self._acquire_memory(user_key):
            yield self.stats()

    @contextmanager
    def _acquire_memory(self, user_key: str) -> Iterator[None]:
        if self._user_limiter.is_limited(user_key):
            raise QueryRateLimitedError("query rate limit exceeded")
        self._user_limiter.record(user_key)

        acquired = False
        queued = False
        try:
            acquired = self._semaphore.acquire(blocking=False)
            if not acquired:
                with self._state_lock:
                    if self._waiting >= self._max_waiting:
                        raise QueryOverloadedError("query queue full")
                    self._waiting += 1
                    queued = True
                acquired = self._semaphore.acquire(timeout=self._acquire_timeout_s)
            if not acquired:
                raise QueryOverloadedError("query queue timeout")
            with self._state_lock:
                if queued:
                    self._waiting -= 1
                self._inflight += 1
            yield
        finally:
            if acquired:
                with self._state_lock:
                    self._inflight = max(0, self._inflight - 1)
                self._semaphore.release()
            elif queued:
                with self._state_lock:
                    self._waiting = max(0, self._waiting - 1)

    @contextmanager
    def _acquire_redis(self, user_key: str) -> Iterator[None]:
        client = _get_redis_client()
        if client is None:
            with self._acquire_memory(user_key):
                yield
            return

        user_rate_key = f"qguard:rate:{user_key}"
        inflight_key = "qguard:inflight"
        waiting_key = "qguard:waiting"
        acquired = False
        queued = False
        started = time.monotonic()
        try:
            # per-user sliding window approximation with fixed window counter
            try:
                current = int(client.incr(user_rate_key))
                if current == 1:
                    client.expire(user_rate_key, self._window_seconds)
                if current > self._max_per_user:
                    raise QueryRateLimitedError("query rate limit exceeded")
            except QueryRateLimitedError:
                raise
            except Exception:
                with self._acquire_memory(user_key):
                    yield
                return

            # distributed concurrency gate with bounded waiting
            while True:
                try:
                    inflight = int(client.incr(inflight_key))
                    if inflight == 1:
                        client.expire(inflight_key, max(5, self._window_seconds))
                    if inflight <= self._max_concurrent:
                        acquired = True
                        break
                    client.decr(inflight_key)
                except Exception:
                    with self._acquire_memory(user_key):
                        yield
                    return

                if not queued:
                    if self._max_waiting <= 0:
                        raise QueryOverloadedError("query queue full")
                    try:
                        waiting = int(client.incr(waiting_key))
                        if waiting == 1:
                            client.expire(waiting_key, max(5, self._window_seconds))
                        if waiting > self._max_waiting:
                            client.decr(waiting_key)
                            raise QueryOverloadedError("query queue full")
                        queued = True
                    except QueryOverloadedError:
                        raise
                    except Exception:
                        with self._acquire_memory(user_key):
                            yield
                        return
                if (time.monotonic() - started) > self._acquire_timeout_s:
                    raise QueryOverloadedError("query queue timeout")
                time.sleep(0.05)
            yield
        finally:
            if queued:
                try:
                    client.decr(waiting_key)
                except Exception:
                    pass
            if acquired:
                try:
                    client.decr(inflight_key)
                except Exception:
                    pass
