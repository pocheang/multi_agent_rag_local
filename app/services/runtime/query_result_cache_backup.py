from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from typing import Any

from app.core.config import get_settings
from app.services.runtime.resilience import TTLCache

logger = logging.getLogger(__name__)

_REDIS_CLIENT = None
_REDIS_LOCK = threading.Lock()
_REDIS_UNAVAILABLE_UNTIL = 0.0


def _redis_retry_cooldown_seconds() -> float:
    settings = get_settings()
    return max(1.0, float(getattr(settings, "redis_retry_cooldown_seconds", 15) or 15))


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
        retrieval_strategy: str,
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
            "st": retrieval_strategy,
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
        èŽ·å–ç¼“å­˜æ•°æ®ï¼Œå¹¶éªŒè¯ç”¨æˆ·å½’å±žã€‚

        Args:
            key: ç¼“å­˜é”®
            session_id: å¯é€‰çš„ä¼šè¯ID
            user_id: å¯é€‰çš„ç”¨æˆ·IDï¼Œç”¨äºŽéªŒè¯ç¼“å­˜å½’å±ž

        Returns:
            ç¼“å­˜æ•°æ®ï¼Œå¦‚æžœéªŒè¯å¤±è´¥åˆ™è¿”å›ž None
        """
        if self._effective_backend() == "off":
            return None

        # P0 FIX: 强制要求 user_id，防止缓存隔离绕过
        if not user_id:
            logger.warning("Cache get without user_id is rejected for security isolation")
            return None

        if session_id:
            v = self._session_memory.get(f"session:{session_id}:{key}")
            if isinstance(v, dict):
                # éªŒè¯ç”¨æˆ·å½’å±ž
                if user_id and v.get("user_id") != user_id:
                    logger.warning(
                        "Cache ownership mismatch (session): key=%s, expected_user=%s, cached_user=%s",
                        key,
                        user_id,
                        v.get("user_id"),
                    )
                    return None
                return v
        backend = self._effective_backend()
        if backend == "redis":
            client = _get_redis_client()
            if client is not None:
                try:
                    raw = client.get(f"qcache:{key}")
                    if raw:
                        data = json.loads(raw)
                        if isinstance(data, dict):
                            # éªŒè¯ç”¨æˆ·å½’å±ž
                            if user_id and data.get("user_id") != user_id:
                                logger.warning(
                                    "Cache ownership mismatch (redis): key=%s, expected_user=%s, cached_user=%s",
                                    key,
                                    user_id,
                                    data.get("user_id"),
                                )
                                return None
                            return data
                except (json.JSONDecodeError, ValueError, TypeError, OSError):
                    logger.warning("query_cache_get_failed key=%s", key, exc_info=True)
        v = self._memory.get(key)
        if isinstance(v, dict):
            # éªŒè¯ç”¨æˆ·å½’å±ž
            if user_id and v.get("user_id") != user_id:
                logger.warning(
                    "Cache ownership mismatch (memory): key=%s, expected_user=%s, cached_user=%s",
                    key,
                    user_id,
                    v.get("user_id"),
                )
                return None
            return v
        return None

    def set(self, key: str, value: dict[str, Any], session_id: str | None = None, user_id: str | None = None) -> None:
        """
        ä¿å­˜ç¼“å­˜æ•°æ®ï¼Œå¼ºåˆ¶åŒ…å«ç”¨æˆ·IDä»¥ç¡®ä¿éš”ç¦»ã€‚

        Args:
            key: ç¼“å­˜é”®
            value: ç¼“å­˜å€¼
            session_id: å¯é€‰çš„ä¼šè¯ID
            user_id: å¯é€‰çš„ç”¨æˆ·IDï¼Œå°†è¢«ä¿å­˜åˆ°ç¼“å­˜æ•°æ®ä¸­
        """
        if self._effective_backend() == "off":
            return

        # åˆ›å»ºç¼“å­˜æ•°æ®å‰¯æœ¬å¹¶ç¡®ä¿åŒ…å« user_id
        cache_value = dict(value)
        if user_id:
            cache_value["user_id"] = user_id

        self._memory.set(key, cache_value)
        if session_id:
            self._session_memory.set(f"session:{session_id}:{key}", cache_value)
        if self._effective_backend() == "redis":
            client = _get_redis_client()
            if client is not None:
                try:
                    client.setex(f"qcache:{key}", self._ttl_seconds, json.dumps(cache_value, ensure_ascii=False))
                except (json.JSONDecodeError, ValueError, TypeError, OSError):
                    logger.warning("query_cache_set_failed key=%s", key, exc_info=True)

    def mark_inflight(self, key: str) -> bool:
        now = time.time()
        backend = self._effective_backend()
        with self._lock:
            # gc old inflight marks
            stale = [k for k, ts in self._inflight.items() if (now - ts) > self._ttl_seconds]
            for s in stale:
                self._inflight.pop(s, None)
                self._inflight_tokens.pop(s, None)
            if key in self._inflight:
                return False
            if backend == "redis":
                client = _get_redis_client()
                if client is not None:
                    token = hashlib.sha256(f"{key}:{now}".encode()).hexdigest()
                    try:
                        locked = bool(
                            client.set(
                                f"qinflight:{key}",
                                token,
                                nx=True,
                                ex=max(1, int(self._ttl_seconds)),
                            )
                        )
                    except (ValueError, TypeError, OSError):
                        logger.warning("query_inflight_lock_failed key=%s", key, exc_info=True)
                        locked = False
                    if not locked:
                        return False
                    self._inflight_tokens[key] = token
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
                except (ValueError, TypeError, OSError):
                    logger.warning("query_inflight_clear_failed key=%s", key, exc_info=True)

    def is_inflight(self, key: str) -> bool:
        backend = self._effective_backend()
        if backend == "redis":
            client = _get_redis_client()
            if client is not None:
                try:
                    return bool(client.exists(f"qinflight:{key}"))
                except (ValueError, TypeError, OSError):
                    logger.warning("query_inflight_check_failed key=%s", key, exc_info=True)
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
                except (json.JSONDecodeError, ValueError, TypeError, OSError):
                    logger.warning("query_stream_get_failed key=%s", key, exc_info=True)
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
                except (json.JSONDecodeError, ValueError, TypeError, OSError):
                    logger.warning("query_stream_append_failed key=%s", key, exc_info=True)

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
                except (json.JSONDecodeError, ValueError, TypeError, OSError):
                    logger.warning("query_stream_done_failed key=%s", key, exc_info=True)
