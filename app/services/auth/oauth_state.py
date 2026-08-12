"""Storage and validation for short-lived OAuth CSRF state."""

import json
import logging
import secrets
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


class OAuthStateStore:
    """Persist OAuth state in Redis when available, with an in-process fallback."""

    _MAX_MEMORY_ENTRIES = 1_024

    def __init__(self, redis_url: str | None):
        self.redis_url = redis_url or "redis://localhost:6379/0"
        self._memory: dict[str, tuple[float, dict[str, Any]]] = {}
        # A single re-entrant lock makes the Redis/memory hand-off a one-time
        # operation inside this process while still allowing the helpers below
        # to be used from the consume path.
        self._memory_lock = threading.RLock()

    def create(self, data: dict[str, Any], ttl_seconds: int = 300) -> str:
        state = secrets.token_urlsafe(32)
        self.store(state, data, ttl_seconds=ttl_seconds)
        return state

    def store(self, state: str, data: dict[str, Any], ttl_seconds: int = 300) -> None:
        redis_client = self._redis_client()
        if redis_client:
            try:
                redis_client.setex(f"oauth_state:{state}", ttl_seconds, json.dumps(data))
                return
            except Exception as exc:
                logger.warning("Failed to store OAuth state in Redis: %s", exc)
        expires_at = time.monotonic() + max(0, ttl_seconds)
        with self._memory_lock:
            self._prune_memory_locked()
            if state not in self._memory:
                while len(self._memory) >= self._MAX_MEMORY_ENTRIES:
                    oldest_state = min(self._memory, key=lambda key: self._memory[key][0])
                    self._memory.pop(oldest_state, None)
            self._memory[state] = (expires_at, data)

    def consume(self, state: str | None, client_ip: str) -> tuple[str | None, str | None]:
        """Consume state once and return a callback error code and stored IP."""
        data = self._consume(state) if state else None
        if not state or not data:
            return "invalid_state", None
        stored_ip = data.get("ip")
        if stored_ip != client_ip:
            return "security_check_failed", str(stored_ip)
        return None, str(stored_ip)

    def get(self, state: str) -> dict[str, Any] | None:
        redis_client = self._redis_client()
        if redis_client:
            try:
                value = redis_client.get(f"oauth_state:{state}")
                if value:
                    return json.loads(value)
            except Exception as exc:
                logger.warning("Failed to get OAuth state from Redis: %s", exc)
        return self._get_memory(state)

    def delete(self, state: str) -> None:
        redis_client = self._redis_client()
        if redis_client:
            try:
                redis_client.delete(f"oauth_state:{state}")
            except Exception:
                pass
        with self._memory_lock:
            self._memory.pop(state, None)

    def _consume(self, state: str) -> dict[str, Any] | None:
        """Atomically retrieve and delete state from the active backing store."""
        with self._memory_lock:
            redis_client = self._redis_client()
            if redis_client:
                try:
                    value = self._redis_getdel(redis_client, f"oauth_state:{state}")
                    if value:
                        # Clear a possible fallback entry before returning so a
                        # stale local copy cannot be replayed later.
                        self._pop_memory(state)
                        return json.loads(value)
                except Exception as exc:
                    logger.warning("Failed to consume OAuth state from Redis: %s", exc)
            # Redis GETDEL/Lua/WATCH may legitimately find nothing (or be
            # unavailable).  The protected in-process copy remains the fallback.
            return self._pop_memory(state)

    @staticmethod
    def _redis_getdel(redis_client: Any, key: str) -> str | None:
        """Use GETDEL where available, falling back to an atomic Redis script."""
        getdel = getattr(redis_client, "getdel", None)
        if callable(getdel):
            try:
                return getdel(key)
            except Exception as exc:
                # Older Redis servers can reject GETDEL even when a client exposes it.
                if "unknown command" not in str(exc).lower():
                    raise
        eval_command = getattr(redis_client, "eval", None)
        if callable(eval_command):
            try:
                return eval_command(
                    "local value = redis.call('GET', KEYS[1]); "
                    "if value then redis.call('DEL', KEYS[1]); end; "
                    "return value",
                    1,
                    key,
                )
            except Exception as exc:
                if "unknown command" not in str(exc).lower():
                    raise
        return OAuthStateStore._redis_transactional_getdel(redis_client, key)

    @staticmethod
    def _redis_transactional_getdel(redis_client: Any, key: str) -> str | None:
        """Atomically consume state on Redis deployments where Lua is unavailable."""
        pipeline = redis_client.pipeline()
        try:
            for _ in range(3):
                try:
                    pipeline.watch(key)
                    value = pipeline.get(key)
                    pipeline.multi()
                    pipeline.delete(key)
                    pipeline.execute()
                    return value
                except Exception as exc:
                    if exc.__class__.__name__ != "WatchError":
                        raise
                finally:
                    pipeline.reset()
        finally:
            pipeline.reset()
        raise RuntimeError("OAuth state changed during atomic consumption")

    def _get_memory(self, state: str) -> dict[str, Any] | None:
        with self._memory_lock:
            entry = self._memory.get(state)
            if entry is None:
                return None
            expires_at, data = entry
            if expires_at <= time.monotonic():
                self._memory.pop(state, None)
                return None
            return data

    def _prune_memory_locked(self) -> None:
        now_monotonic = time.monotonic()
        expired_states = [
            state for state, (expires_at, _) in self._memory.items() if expires_at <= now_monotonic
        ]
        for expired_state in expired_states:
            self._memory.pop(expired_state, None)

    def _pop_memory(self, state: str) -> dict[str, Any] | None:
        with self._memory_lock:
            entry = self._memory.pop(state, None)
            if entry is None:
                return None
            expires_at, data = entry
            if expires_at <= time.monotonic():
                return None
            return data

    def _redis_client(self):
        try:
            import redis

            return redis.from_url(
                self.redis_url,
                decode_responses=True,
                socket_connect_timeout=0.5,
                socket_timeout=0.5,
            )
        except Exception as exc:
            logger.warning("Redis not available for OAuth state storage: %s", exc)
            return None
