from __future__ import annotations

import asyncio
import logging
import sys
import threading
import time
from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass

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


def _redis_is_cooling_down() -> bool:
    return bool(_REDIS_UNAVAILABLE_UNTIL and time.monotonic() < _REDIS_UNAVAILABLE_UNTIL)


def _drop_redis_client() -> None:
    """Discard the client and stop trying until the cooldown expires.

    Call under ``_REDIS_LOCK``. ``from_url`` can succeed and ``ping`` still fail,
    so there may be a client to close even though the connection never worked.
    """

    global _REDIS_CLIENT, _REDIS_UNAVAILABLE_UNTIL
    if _REDIS_CLIENT is not None:
        try:
            _REDIS_CLIENT.close()
        except Exception as cleanup_error:
            logger.debug(f"Redis cleanup failed while dropping the client: {cleanup_error}")
        _REDIS_CLIENT = None
    _REDIS_UNAVAILABLE_UNTIL = time.monotonic() + _redis_retry_cooldown_seconds()


def _connect_redis():
    """Open the shared client, or start a cooldown. Call under ``_REDIS_LOCK``."""

    global _REDIS_CLIENT, _REDIS_UNAVAILABLE_UNTIL
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
        # Not installed, or not the shape we expect -- routine, and not worth a warning.
        logger.debug(f"Redis not available for query guard: {e}")
    except Exception as e:
        logger.warning(f"Redis connection failed for query guard: {e}", exc_info=True)
    _drop_redis_client()
    return None


def _get_redis_client():
    """The process-wide client, opened once and not retried during a cooldown.

    Checked before and again inside the lock: the wait for the lock is exactly
    as long as another thread's connection attempt, which is the case worth not
    repeating.
    """

    if _REDIS_CLIENT is not None:
        return _REDIS_CLIENT
    if _redis_is_cooling_down():
        return None
    with _REDIS_LOCK:
        if _REDIS_CLIENT is not None:
            return _REDIS_CLIENT
        if _redis_is_cooling_down():
            return None
        return _connect_redis()


_INFLIGHT_KEY = "qguard:inflight"
_WAITING_KEY = "qguard:waiting"


@dataclass
class _RedisSlot:
    """What one acquisition has taken from the shared counters.

    The release path runs whether the acquisition succeeded, was refused or
    degraded to the in-memory guard, so it has to be told what to give back
    rather than infer it.
    """

    user_rate_key: str
    acquired: bool = False
    queued: bool = False


def _queue_backoff_seconds(elapsed: float) -> float:
    """Widen the poll interval as a wait lengthens, so a full queue does not spin."""

    if elapsed < 0.5:
        return 0.05
    if elapsed < 2.0:
        return 0.1
    if elapsed < 5.0:
        return 0.2
    return 0.5


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
                    inflight = int(client.get(_INFLIGHT_KEY) or 0)
                    waiting = int(client.get(_WAITING_KEY) or 0)
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

        slot = _RedisSlot(user_rate_key=f"qguard:rate:{user_key}")
        try:
            if self._reserve_redis_slot(client, slot, user_key):
                yield
            else:
                # Redis stopped answering partway through. Degrading to the
                # in-memory guard keeps the request alive; the release below
                # still gives back whatever had already been counted.
                with self._acquire_memory(user_key):
                    yield
        finally:
            self._release_redis_slot(client, slot, user_key)

    def _reserve_redis_slot(self, client, slot: _RedisSlot, user_key: str) -> bool:
        """Take a slot, or say the cluster counters are unusable.

        Returns False only for "Redis is not answering" -- a refusal is an
        exception, so a caller cannot mistake being turned away for degrading.
        """

        if not self._within_user_rate(client, slot, user_key):
            return False

        started = time.monotonic()
        while True:
            taken = self._take_inflight(client, slot)
            if taken is None:
                return False
            if taken:
                return True
            if not slot.queued and not self._join_queue(client, slot):
                return False
            if (time.monotonic() - started) > self._acquire_timeout_s:
                raise QueryOverloadedError("query queue timeout")
            time.sleep(_queue_backoff_seconds(time.monotonic() - started))

    def _within_user_rate(self, client, slot: _RedisSlot, user_key: str) -> bool:
        """A fixed-window counter approximating a sliding window, shared by every worker."""

        try:
            current = int(client.incr(slot.user_rate_key))
            if current == 1:
                client.expire(slot.user_rate_key, self._window_seconds)
            if current > self._max_per_user:
                raise QueryRateLimitedError("query rate limit exceeded")
        except QueryRateLimitedError:
            raise
        except (ValueError, TypeError, OSError) as e:
            logger.debug("query_guard_rate_check_failed user=%s error=%s", key_ref(user_key), str(e))
            return False
        return True

    def _take_inflight(self, client, slot: _RedisSlot) -> bool | None:
        """True when the slot is ours, False when the gate is full, None when Redis is unusable.

        The probe increments first and gives the count back when it overshoots,
        which is what makes the check atomic across workers.
        """

        try:
            inflight = int(client.incr(_INFLIGHT_KEY))
            if inflight == 1:
                client.expire(_INFLIGHT_KEY, max(5, self._window_seconds))
            if inflight <= self._max_concurrent:
                slot.acquired = True
                return True
            client.decr(_INFLIGHT_KEY)
            return False
        except (ValueError, TypeError, OSError) as e:
            logger.debug(f"Redis inflight increment failed: {e}")
            return None

    def _join_queue(self, client, slot: _RedisSlot) -> bool:
        """Claim a place in the bounded queue. Raises when there is none; False when Redis is unusable."""

        if self._max_waiting <= 0:
            raise QueryOverloadedError("query queue full")
        try:
            waiting = int(client.incr(_WAITING_KEY))
            if waiting == 1:
                client.expire(_WAITING_KEY, max(5, self._window_seconds))
            if waiting > self._max_waiting:
                client.decr(_WAITING_KEY)
                raise QueryOverloadedError("query queue full")
            slot.queued = True
            return True
        except QueryOverloadedError:
            raise
        except (ValueError, TypeError, OSError) as e:
            logger.debug(f"Redis waiting queue increment failed: {e}")
            return False

    def _release_redis_slot(self, client, slot: _RedisSlot, user_key: str) -> None:
        if slot.queued:
            self._give_back(client, _WAITING_KEY, name="waiting", limit=self._max_waiting, user_key=user_key)
        if slot.acquired:
            self._give_back(client, _INFLIGHT_KEY, name="inflight", limit=self._max_concurrent, user_key=user_key)

    def _give_back(self, client, key: str, *, name: str, limit: int, user_key: str) -> None:
        """Return a shared counter, and repair it if the decrement will not land.

        These keys outlive the request that incremented them, so a decrement lost
        to a blip costs the whole cluster that much capacity until the key
        expires. A count past twice the limit is not a busy moment, it is a leak.
        """

        try:
            client.decr(key)
            return
        except (ValueError, TypeError, OSError) as e:
            logger.warning(
                "query_guard_%s_decr_failed user=%s error=%s", name, key_ref(user_key), str(e), exc_info=True
            )

        try:
            current = int(client.get(key) or 0)
            if current > limit * 2:
                logger.exception(f"Resetting corrupted {name} counter: {current}")
                client.set(key, 0, ex=max(5, self._window_seconds))
        except Exception as reset_error:
            logger.warning(f"Failed to reset {name} counter: {reset_error}")
