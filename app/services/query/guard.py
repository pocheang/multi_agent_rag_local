from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager

from app.core.config import get_settings
from app.services.observability.log_safety import key_ref
from app.services.security.rate_limiter import SlidingWindowLimiter

logger = logging.getLogger(__name__)


class QueryRateLimitedError(RuntimeError):
    pass


class QueryOverloadedError(RuntimeError):
    pass


_REDIS_CLIENT = None
_REDIS_LOCK = threading.Lock()
_REDIS_UNAVAILABLE_UNTIL = 0.0


def _redis_retry_cooldown_seconds() -> float:
    settings = get_settings()
    return max(1.0, float(getattr(settings, "redis_retry_cooldown_seconds", 15) or 15))


def _get_redis_client():
    global _REDIS_CLIENT, _REDIS_UNAVAILABLE_UNTIL
    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT
    if _REDIS_UNAVAILABLE_UNTIL and time.monotonic() < _REDIS_UNAVAILABLE_UNTIL:
        return None
    with _REDIS_LOCK:
        if _REDIS_CLIENT is not None:
            return _REDIS_CLIENT
        if _REDIS_UNAVAILABLE_UNTIL and time.monotonic() < _REDIS_UNAVAILABLE_UNTIL:
            return None
        settings = get_settings()
        try:
            import redis  # type: ignore

            _REDIS_CLIENT = redis.from_url(
                str(getattr(settings, "redis_url", "")),
                decode_responses=True,
                socket_connect_timeout=0.2,
                socket_timeout=0.2,
                retry_on_timeout=False,
                max_connections=50,  # Add connection pool
                health_check_interval=30,
            )
            _REDIS_CLIENT.ping()
            _REDIS_UNAVAILABLE_UNTIL = 0.0
            return _REDIS_CLIENT
        except (ImportError, AttributeError) as e:
            logger.debug(f"Redis not available for query guard: {e}")
            if _REDIS_CLIENT is not None:
                try:
                    _REDIS_CLIENT.close()
                except Exception as cleanup_error:
                    logger.debug(f"Redis cleanup failed during init error: {cleanup_error}")
                _REDIS_CLIENT = None
            _REDIS_UNAVAILABLE_UNTIL = time.monotonic() + _redis_retry_cooldown_seconds()
            return None
        except Exception as e:
            logger.warning(f"Redis connection failed for query guard: {e}", exc_info=True)
            if _REDIS_CLIENT is not None:
                try:
                    _REDIS_CLIENT.close()
                except Exception as cleanup_error:
                    logger.debug(f"Redis cleanup failed during connection error: {cleanup_error}")
                _REDIS_CLIENT = None
            _REDIS_UNAVAILABLE_UNTIL = time.monotonic() + _redis_retry_cooldown_seconds()
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
                except (ValueError, TypeError, OSError) as e:
                    logger.debug(f"Failed to get query guard stats from Redis: {e}")
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

    @asynccontextmanager
    async def acquire_async(self, user_key: str) -> AsyncIterator[dict[str, int | str]]:
        """Acquire a slot without blocking the event loop.

        ``acquire`` waits on a threading semaphore for up to
        ``acquire_timeout_ms``, and the redis backend does blocking I/O.  Running
        either inline in an async handler freezes every other task on the loop
        precisely when the server is overloaded, so both the blocking enter and
        the blocking exit run in worker threads.
        """
        manager = self.acquire(user_key)
        stats = await asyncio.to_thread(manager.__enter__)
        exc_info: tuple = (None, None, None)
        try:
            yield stats
        except BaseException:
            exc_info = sys.exc_info()
            raise
        finally:
            await asyncio.to_thread(manager.__exit__, *exc_info)

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
            except (ValueError, TypeError, OSError) as e:
                logger.debug("query_guard_rate_check_failed user=%s error=%s", key_ref(user_key), str(e))
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
                except (ValueError, TypeError, OSError) as e:
                    logger.debug(f"Redis inflight increment failed: {e}")
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
                    except (ValueError, TypeError, OSError) as e:
                        logger.debug(f"Redis waiting queue increment failed: {e}")
                        with self._acquire_memory(user_key):
                            yield
                        return
                if (time.monotonic() - started) > self._acquire_timeout_s:
                    raise QueryOverloadedError("query queue timeout")

                # OPTIMIZATION: Exponential backoff instead of fixed 50ms spin-wait
                # Reduces CPU usage under high load
                elapsed = time.monotonic() - started
                if elapsed < 0.5:
                    sleep_time = 0.05  # 50ms for first 0.5s
                elif elapsed < 2.0:
                    sleep_time = 0.1  # 100ms for next 1.5s
                elif elapsed < 5.0:
                    sleep_time = 0.2  # 200ms for next 3s
                else:
                    sleep_time = 0.5  # 500ms after 5s
                time.sleep(sleep_time)
            yield
        finally:
            if queued:
                try:
                    client.decr(waiting_key)
                except (ValueError, TypeError, OSError) as e:
                    logger.warning(
                        "query_guard_waiting_decr_failed user=%s error=%s", key_ref(user_key), str(e), exc_info=True
                    )
                    # Attempt to reset the counter if decrement fails repeatedly
                    try:
                        current_waiting = int(client.get(waiting_key) or 0)
                        if current_waiting > self._max_waiting * 2:
                            logger.error(f"Resetting corrupted waiting counter: {current_waiting}")
                            client.set(waiting_key, 0, ex=max(5, self._window_seconds))
                    except Exception as reset_error:
                        logger.warning(f"Failed to reset waiting counter: {reset_error}")
            if acquired:
                try:
                    client.decr(inflight_key)
                except (ValueError, TypeError, OSError) as e:
                    logger.warning(
                        "query_guard_inflight_decr_failed user=%s error=%s", key_ref(user_key), str(e), exc_info=True
                    )
                    # Attempt to reset the counter if decrement fails repeatedly
                    try:
                        current_inflight = int(client.get(inflight_key) or 0)
                        if current_inflight > self._max_concurrent * 2:
                            logger.error(f"Resetting corrupted inflight counter: {current_inflight}")
                            client.set(inflight_key, 0, ex=max(5, self._window_seconds))
                    except Exception as reset_error:
                        logger.warning(f"Failed to reset inflight counter: {reset_error}")
