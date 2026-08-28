from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from typing import Any

from app.core.config import get_settings
from app.services.runtime.resilience import TTLCache

try:
    from redis.exceptions import RedisError
except ImportError:  # pragma: no cover - Redis is an optional backend

    class RedisError(Exception):
        """Fallback type used when redis-py is not installed."""


logger = logging.getLogger(__name__)

_REDIS_CLIENT = None
_REDIS_LOCK = threading.Lock()
_REDIS_UNAVAILABLE_UNTIL = 0.0


def _redis_retry_cooldown_seconds() -> float:
    settings = get_settings()
    return max(1.0, float(getattr(settings, "redis_retry_cooldown_seconds", 15) or 15))


def _mark_redis_unavailable(exc: BaseException) -> None:
    """Drop a failed client so cache operations can degrade to memory."""
    global _REDIS_CLIENT, _REDIS_UNAVAILABLE_UNTIL
    with _REDIS_LOCK:
        client = _REDIS_CLIENT
        _REDIS_CLIENT = None
        _REDIS_UNAVAILABLE_UNTIL = time.monotonic() + _redis_retry_cooldown_seconds()
    if client is not None:
        try:
            client.close()
        except Exception:
            pass
    logger.warning("Redis query cache unavailable; using memory cache: %s", exc)


def _get_redis_client():
    """
    Get or create Redis client with proper connection pooling and error handling.

    P0 FIX: Improved timeout configuration and connection cleanup.
    """
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

            # P0 FIX: Increased timeouts from 0.2s to 2s for stability
            # Added retry_on_timeout and socket_keepalive for resilience
            _REDIS_CLIENT = redis.from_url(
                str(getattr(settings, "redis_url", "")),
                decode_responses=True,
                socket_connect_timeout=2.0,  # Increased from 0.2s
                socket_timeout=2.0,  # Increased from 0.2s
                retry_on_timeout=True,  # Enable retry on transient failures
                max_connections=50,
                health_check_interval=30,
                socket_keepalive=True,  # Keep connections alive
            )
            _REDIS_CLIENT.ping()
            _REDIS_UNAVAILABLE_UNTIL = 0.0
            logger.info("Redis client initialized successfully for query result cache")
            return _REDIS_CLIENT
        except (ImportError, AttributeError) as e:
            logger.debug(f"Redis not available for query result cache: {e}")
            if _REDIS_CLIENT is not None:
                try:
                    _REDIS_CLIENT.close()
                except Exception as cleanup_error:
                    logger.debug(f"Redis cleanup failed during init error: {cleanup_error}")
                _REDIS_CLIENT = None
            _REDIS_UNAVAILABLE_UNTIL = time.monotonic() + _redis_retry_cooldown_seconds()
            return None
        except Exception as e:
            logger.warning(f"Redis connection failed for query result cache: {e}", exc_info=True)
            if _REDIS_CLIENT is not None:
                try:
                    _REDIS_CLIENT.close()
                except Exception as cleanup_error:
                    logger.debug(f"Redis cleanup failed during connection error: {cleanup_error}")
                _REDIS_CLIENT = None
            _REDIS_UNAVAILABLE_UNTIL = time.monotonic() + _redis_retry_cooldown_seconds()
            return None


class QueryResultCache:
    def __init__(
        self,
        *,
        backend: str,
        ttl_seconds: int,
        max_items: int,
        session_ttl_seconds: int,
    ):
        b = str(backend or "auto").strip().lower()
        if b not in {"auto", "memory", "redis", "off"}:
            b = "auto"
        self._backend = b
        self._ttl_seconds = max(1, int(ttl_seconds))
        self._session_ttl_seconds = max(1, int(session_ttl_seconds))
        self._memory = TTLCache(ttl_seconds=self._ttl_seconds, max_items=max(1, int(max_items)))
        self._session_memory = TTLCache(ttl_seconds=self._session_ttl_seconds, max_items=max(1, int(max_items)))
        self._stream_memory = TTLCache(
            ttl_seconds=max(1, int(getattr(get_settings(), "stream_replay_cache_ttl_seconds", 600) or 600)),
            max_items=max(1, int(max_items)),
        )
        self._stream_max_events = max(1, int(getattr(get_settings(), "stream_replay_cache_max_events", 1200) or 1200))
        self._lock = threading.Lock()
        self._inflight: dict[str, float] = {}
        self._inflight_tokens: dict[str, str] = {}

    def _effective_backend(self) -> str:
        if self._backend == "off":
            return "off"
        if self._backend == "memory":
            return "memory"
        if self._backend == "redis":
            return "redis" if _get_redis_client() is not None else "memory"
        return "redis" if _get_redis_client() is not None else "memory"

    @staticmethod
    def build_key(
        *,
        user_id: str,
        session_id: str,
        question: str,
        use_web_fallback: bool,
        use_reasoning: bool,
        agent_class_hint: str,
        mode: str = "query",
        request_id: str = "",
        include_request_id: bool = False,
        index_fingerprint: str = "",
    ) -> str:
        payload: dict[str, Any] = {
            "u": user_id,
            "s": session_id,
            "q": question,
            "w": bool(use_web_fallback),
            "r": bool(use_reasoning),
            "a": agent_class_hint,
            "m": str(mode or "query"),
            "idx": str(index_fingerprint or ""),
        }
        if include_request_id:
            payload["rid"] = request_id
        raw = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, key: str, session_id: str | None = None, user_id: str | None = None) -> dict[str, Any] | None:
        """
        Get cached data with user ownership verification.

        P0 FIX: Enforce user_id requirement to prevent cache isolation bypass.

        Args:
            key: Cache key
            session_id: Optional session ID
            user_id: REQUIRED user ID for cache ownership verification (P0 FIX: now required)

        Returns:
            Cached data, or None if verification fails or user_id is missing
        """
        if self._effective_backend() == "off":
            return None

        # P0 FIX: Enforce user_id requirement to prevent cache isolation bypass
        if not user_id:
            logger.warning("Cache get without user_id is rejected for security isolation")
            return None

        # Check session cache
        if session_id:
            v = self._session_memory.get(f"session:{session_id}:{key}")
            if isinstance(v, dict):
                # P0 FIX: Strict user ownership verification (removed "if user_id and")
                if v.get("user_id") != user_id:
                    logger.warning(
                        "Cache ownership mismatch (session): key=%s, expected_user=%s, cached_user=%s",
                        key[:16],
                        user_id,
                        v.get("user_id"),
                    )
                    return None
                return v

        # Check Redis cache
        backend = self._effective_backend()
        if backend == "redis":
            client = _get_redis_client()
            if client is not None:
                try:
                    # P0 FIX: Redis key includes user_id for isolation
                    raw = client.get(f"qcache:{user_id}:{key}")
                    if raw:
                        data = json.loads(raw)
                        if isinstance(data, dict):
                            # P0 FIX: Double verification of user ownership
                            if data.get("user_id") != user_id:
                                logger.error(
                                    "SECURITY: Cache ownership mismatch in Redis: key=%s, expected_user=%s, cached_user=%s",
                                    key[:16],
                                    user_id,
                                    data.get("user_id"),
                                )
                                # Delete poisoned cache
                                try:
                                    client.delete(f"qcache:{user_id}:{key}")
                                except Exception:
                                    pass
                                return None
                            return data
                except RedisError as exc:
                    _mark_redis_unavailable(exc)
                    logger.warning("query_cache_get_failed key=%s", key[:16], exc_info=True)
                except (json.JSONDecodeError, ValueError, TypeError, OSError):
                    logger.warning("query_cache_get_failed key=%s", key[:16], exc_info=True)

        # Check memory cache
        v = self._memory.get(key)
        if isinstance(v, dict):
            # P0 FIX: Strict user ownership verification
            if v.get("user_id") != user_id:
                logger.warning(
                    "Cache ownership mismatch (memory): key=%s, expected_user=%s, cached_user=%s",
                    key[:16],
                    user_id,
                    v.get("user_id"),
                )
                return None
            return v
        return None

    def set(self, key: str, value: dict[str, Any], session_id: str | None = None, user_id: str | None = None) -> None:
        """
        Store cache data with enforced user ID for isolation.

        P0 FIX: Enforce user_id requirement and include it in Redis keys.

        Args:
            key: Cache key
            value: Cache value
            session_id: Optional session ID
            user_id: REQUIRED user ID for cache isolation (P0 FIX: now required)
        """
        if self._effective_backend() == "off":
            return

        # P0 FIX: Enforce user_id requirement
        if not user_id:
            logger.error("Cache set without user_id is rejected for security isolation")
            return

        # Create cache value copy and ensure user_id is included
        cache_value = dict(value)
        cache_value["user_id"] = user_id

        self._memory.set(key, cache_value)
        if session_id:
            self._session_memory.set(f"session:{session_id}:{key}", cache_value)
        if self._effective_backend() == "redis":
            client = _get_redis_client()
            if client is not None:
                try:
                    # P0 FIX: Redis key includes user_id for isolation
                    client.setex(
                        f"qcache:{user_id}:{key}", self._ttl_seconds, json.dumps(cache_value, ensure_ascii=False)
                    )
                except RedisError as exc:
                    _mark_redis_unavailable(exc)
                    logger.warning("query_cache_set_failed key=%s", key[:16], exc_info=True)
                except (json.JSONDecodeError, ValueError, TypeError, OSError):
                    logger.warning("query_cache_set_failed key=%s", key[:16], exc_info=True)

    def mark_inflight(self, key: str, user_id: str | None = None) -> bool:
        """
        P0 FIX: Atomic check-and-set for inflight marking to prevent race conditions.
        Added user_id parameter for better isolation.
        """
        now = time.time()
        backend = self._effective_backend()

        # P0 FIX: Hold lock during entire check-and-set operation
        with self._lock:
            # gc old inflight marks
            stale = [k for k, ts in self._inflight.items() if (now - ts) > self._ttl_seconds]
            for s in stale:
                self._inflight.pop(s, None)
                self._inflight_tokens.pop(s, None)

            # P0 FIX: Check happens inside lock
            if key in self._inflight:
                return False

            if backend == "redis":
                client = _get_redis_client()
                if client is not None:
                    token = hashlib.sha256(f"{key}:{now}:{user_id or ''}".encode()).hexdigest()
                    try:
                        locked = bool(
                            client.set(
                                f"qinflight:{key}",
                                token,
                                nx=True,
                                ex=max(1, int(self._ttl_seconds)),
                            )
                        )
                    except RedisError as exc:
                        _mark_redis_unavailable(exc)
                        logger.warning("query_inflight_lock_failed key=%s", key[:16], exc_info=True)
                        locked = True
                    except (ValueError, TypeError, OSError):
                        logger.warning("query_inflight_lock_failed key=%s", key[:16], exc_info=True)
                        locked = True
                    if not locked:
                        return False
                    if _REDIS_CLIENT is not None:
                        self._inflight_tokens[key] = token

            # P0 FIX: Set happens inside lock
            self._inflight[key] = now
            return True

    def clear_inflight(self, key: str) -> None:
        backend = self._effective_backend()
        with self._lock:
            self._inflight.pop(key, None)
            token = self._inflight_tokens.pop(key, None)
        if backend == "redis":
            client = _get_redis_client()
            if client is not None and token:
                try:
                    current = client.get(f"qinflight:{key}")
                    if current == token:
                        client.delete(f"qinflight:{key}")
                except RedisError as exc:
                    _mark_redis_unavailable(exc)
                    logger.warning("query_inflight_clear_failed key=%s", key[:16], exc_info=True)
                except (ValueError, TypeError, OSError):
                    logger.warning("query_inflight_clear_failed key=%s", key[:16], exc_info=True)

    def is_inflight(self, key: str) -> bool:
        backend = self._effective_backend()
        if backend == "redis":
            client = _get_redis_client()
            if client is not None:
                try:
                    return bool(client.exists(f"qinflight:{key}"))
                except RedisError as exc:
                    _mark_redis_unavailable(exc)
                    logger.warning("query_inflight_check_failed key=%s", key[:16], exc_info=True)
                except (ValueError, TypeError, OSError):
                    logger.warning("query_inflight_check_failed key=%s", key[:16], exc_info=True)
        with self._lock:
            return key in self._inflight

    def get_stream_events(self, key: str) -> dict[str, Any]:
        if self._effective_backend() == "off":
            return {"events": [], "done": False}
        backend = self._effective_backend()
        if backend == "redis":
            client = _get_redis_client()
            if client is not None:
                try:
                    raw = client.get(f"qstream:{key}")
                    if raw:
                        data = json.loads(raw)
                        if isinstance(data, dict):
                            return {
                                "events": list(data.get("events", []) or []),
                                "done": bool(data.get("done", False)),
                            }
                except RedisError as exc:
                    _mark_redis_unavailable(exc)
                    logger.warning("query_stream_get_failed key=%s", key[:16], exc_info=True)
                except (json.JSONDecodeError, ValueError, TypeError, OSError):
                    logger.warning("query_stream_get_failed key=%s", key[:16], exc_info=True)
        mem = self._stream_memory.get(key)
        if isinstance(mem, dict):
            return {
                "events": list(mem.get("events", []) or []),
                "done": bool(mem.get("done", False)),
            }
        return {"events": [], "done": False}

    def append_stream_event(self, key: str, event: dict[str, Any], done: bool = False) -> None:
        if self._effective_backend() == "off":
            return
        cur = self.get_stream_events(key)
        events = list(cur.get("events", []) or [])
        events.append(dict(event))
        if len(events) > self._stream_max_events:
            events = events[-self._stream_max_events :]
        row = {"events": events, "done": bool(done or cur.get("done", False))}
        self._stream_memory.set(key, row)
        if self._effective_backend() == "redis":
            client = _get_redis_client()
            if client is not None:
                try:
                    ttl = max(1, int(getattr(get_settings(), "stream_replay_cache_ttl_seconds", 600) or 600))
                    client.setex(f"qstream:{key}", ttl, json.dumps(row, ensure_ascii=False))
                except RedisError as exc:
                    _mark_redis_unavailable(exc)
                    logger.warning("query_stream_append_failed key=%s", key[:16], exc_info=True)
                except (json.JSONDecodeError, ValueError, TypeError, OSError):
                    logger.warning("query_stream_append_failed key=%s", key[:16], exc_info=True)

    def mark_stream_done(self, key: str) -> None:
        cur = self.get_stream_events(key)
        row = {"events": list(cur.get("events", []) or []), "done": True}
        self._stream_memory.set(key, row)
        if self._effective_backend() == "redis":
            client = _get_redis_client()
            if client is not None:
                try:
                    ttl = max(1, int(getattr(get_settings(), "stream_replay_cache_ttl_seconds", 600) or 600))
                    client.setex(f"qstream:{key}", ttl, json.dumps(row, ensure_ascii=False))
                except RedisError as exc:
                    _mark_redis_unavailable(exc)
                    logger.warning("query_stream_done_failed key=%s", key[:16], exc_info=True)
                except (json.JSONDecodeError, ValueError, TypeError, OSError):
                    logger.warning("query_stream_done_failed key=%s", key[:16], exc_info=True)

    def clear_stream_events(self, key: str) -> None:
        """Remove stale replay events after a stream failed before completion."""
        self._stream_memory.delete(key)
        if self._effective_backend() != "redis":
            return
        client = _get_redis_client()
        if client is None:
            return
        try:
            client.delete(f"qstream:{key}")
        except RedisError as exc:
            _mark_redis_unavailable(exc)
            logger.warning("query_stream_clear_failed key=%s", key[:16], exc_info=True)
        except (ValueError, TypeError, OSError):
            logger.warning("query_stream_clear_failed key=%s", key[:16], exc_info=True)
