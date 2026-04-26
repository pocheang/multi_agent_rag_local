from __future__ import annotations

import hashlib
import json
import threading
import time
from typing import Any

from app.core.config import get_settings
from app.services.resilience import TTLCache

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

    def get(self, key: str, session_id: str | None = None) -> dict[str, Any] | None:
        if self._effective_backend() == "off":
            return None
        if session_id:
            v = self._session_memory.get(f"session:{session_id}:{key}")
            if isinstance(v, dict):
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
                            return data
                except Exception:
                    pass
        v = self._memory.get(key)
        return v if isinstance(v, dict) else None

    def set(self, key: str, value: dict[str, Any], session_id: str | None = None) -> None:
        if self._effective_backend() == "off":
            return
        self._memory.set(key, dict(value))
        if session_id:
            self._session_memory.set(f"session:{session_id}:{key}", dict(value))
        if self._effective_backend() == "redis":
            client = _get_redis_client()
            if client is not None:
                try:
                    client.setex(f"qcache:{key}", self._ttl_seconds, json.dumps(value, ensure_ascii=False))
                except Exception:
                    pass

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
                    token = hashlib.sha256(f"{key}:{now}".encode("utf-8")).hexdigest()
                    try:
                        locked = bool(
                            client.set(
                                f"qinflight:{key}",
                                token,
                                nx=True,
                                ex=max(1, int(self._ttl_seconds)),
                            )
                        )
                    except Exception:
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
                except Exception:
                    pass

    def is_inflight(self, key: str) -> bool:
        backend = self._effective_backend()
        if backend == "redis":
            client = _get_redis_client()
            if client is not None:
                try:
                    return bool(client.exists(f"qinflight:{key}"))
                except Exception:
                    pass
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
                except Exception:
                    pass
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
                except Exception:
                    pass

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
                except Exception:
                    pass
