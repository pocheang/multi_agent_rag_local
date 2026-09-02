"""Router decision caching.

Cache versioning: the router cache key includes a version so calibration changes
invalidate it.

This module used to also expose `cached_vector_search`, plus a synthesis cache
and cache stats/clear helpers. All were unreachable, and `cached_vector_search`
was actively dangerous: it built its key from `kwargs.get("allowed_sources")`, so
applying it to a caller that passed `allowed_sources` positionally would have
dropped the isolation dimension from the key and served one user's retrieval
results to another. Removed 2026-08-30 with phase 2 of
docs/superpowers/plans/2026-08-29-user-data-isolation.md.

The store is a plain synchronous TTL/LRU. It used to be the async
`LRUMemoryCache`, driven from this synchronous decorator with
`loop.run_until_complete` -- and `decide_route` runs inside `asyncio.to_thread`,
where there is no event loop, so every worker thread created one with
`new_event_loop()` and never closed it. A route decision is an in-memory
dictionary lookup; it never needed a loop.
"""

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from typing import Any

logger = logging.getLogger(__name__)

# Cache configuration
DEFAULT_ROUTER_CACHE_SIZE = 500
DEFAULT_TTL_SECONDS = 1800  # 30 minutes

# Router cache version - increment when calibration logic changes
ROUTER_CACHE_VERSION = "v2_calibrated"


class _TTLCache:
    """A small synchronous LRU with per-entry expiry.

    Thread-safe: `decide_route` is called from the retrieval thread pool, so two
    requests can reach this concurrently.
    """

    def __init__(self, max_size: int, ttl_seconds: float) -> None:
        self._entries: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._lock = threading.Lock()

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            expires_at, value = entry
            if expires_at <= time.monotonic():
                del self._entries[key]
                return None
            self._entries.move_to_end(key)
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._entries[key] = (time.monotonic() + self._ttl, value)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_size:
                self._entries.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()


_router_decision_cache = _TTLCache(DEFAULT_ROUTER_CACHE_SIZE, DEFAULT_TTL_SECONDS)


def _make_cache_key(*args, **kwargs) -> str:
    """Create a cache key from arguments."""
    payload = {
        "args": args,
        "kwargs": {key: value for key, value in sorted(kwargs.items()) if value is not None},
    }
    key_string = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(key_string.encode("utf-8")).hexdigest()


def clear_router_decision_cache() -> None:
    """Drop every cached route decision. For tests and admin cache resets."""
    _router_decision_cache.clear()


def cached_router_decision(func: Callable) -> Callable:
    """
    Decorator to cache router decisions.

    Cache key includes: question, agent_class_hint, use_reasoning, use_llm_intent,
    and cache version to prevent collisions between different routing configurations
    and calibration versions.

    The key deliberately carries no user identity: a route decision is an intent
    classification over the question text and holds no document content, so it is
    the same answer for every caller. Anything that caches *retrieval results*
    must key on the access scope instead -- see
    app/retrievers/hybrid/caching.py.

    Usage:
        @cached_router_decision
        def decide_route(question: str, ...) -> RouteDecision:
            ...
    """

    def wrapper(question: str, *args, **kwargs):
        cache_key = _make_cache_key(
            "router",
            ROUTER_CACHE_VERSION,  # Include version to invalidate on calibration changes
            question,
            kwargs.get("agent_class_hint"),
            kwargs.get("use_reasoning"),
            kwargs.get("use_llm_intent"),
        )

        cached_result = _router_decision_cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"Router decision cache hit: {cache_key[:16]}")
            return cached_result

        result = func(question, *args, **kwargs)
        _router_decision_cache.set(cache_key, result)
        logger.debug(f"Router decision cache miss: {cache_key[:16]}")
        return result

    return wrapper
