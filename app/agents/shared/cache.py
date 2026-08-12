"""
Shared caching utilities for all RAG agents.

Provides centralized caching for:
- Vector search results
- Router decisions
- Web research results
- Synthesis outputs

Cache versioning: Router cache includes version to support calibration updates.
"""

import hashlib
import logging
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# Cache configuration
DEFAULT_VECTOR_CACHE_SIZE = 200
DEFAULT_ROUTER_CACHE_SIZE = 500
DEFAULT_SYNTHESIS_CACHE_SIZE = 100
DEFAULT_TTL_SECONDS = 1800  # 30 minutes

# Router cache version - increment when calibration logic changes
ROUTER_CACHE_VERSION = "v2_calibrated"


@dataclass
class CacheEntry:
    """Cache entry with value and metadata."""

    value: Any
    created_at: datetime
    hits: int = 0


class SimpleCache:
    """
    Simple LRU cache with TTL support.

    Shared implementation for all agent caching needs.
    """

    def __init__(self, max_size: int = 100, ttl_seconds: int = 1800):
        self.max_size = max_size
        self.ttl = timedelta(seconds=ttl_seconds)
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        """Get value from cache."""
        if key not in self._cache:
            self._misses += 1
            return None

        entry = self._cache[key]

        # Check expiration
        if datetime.now() - entry.created_at > self.ttl:
            logger.debug(f"Cache entry expired: {key[:16]}")
            del self._cache[key]
            self._misses += 1
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        entry.hits += 1
        self._hits += 1

        return entry.value

    def set(self, key: str, value: Any) -> None:
        """Store value in cache."""
        # Remove oldest if at capacity
        if key not in self._cache and len(self._cache) >= self.max_size:
            oldest_key = next(iter(self._cache))
            del self._cache[oldest_key]

        self._cache[key] = CacheEntry(
            value=value,
            created_at=datetime.now(),
        )
        self._cache.move_to_end(key)

    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
        self._hits = 0
        self._misses = 0

    def stats(self) -> dict:
        """Get cache statistics."""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
        }


# Global cache instances
_vector_search_cache = SimpleCache(max_size=DEFAULT_VECTOR_CACHE_SIZE, ttl_seconds=DEFAULT_TTL_SECONDS)

_router_decision_cache = SimpleCache(max_size=DEFAULT_ROUTER_CACHE_SIZE, ttl_seconds=DEFAULT_TTL_SECONDS)

_synthesis_cache = SimpleCache(
    max_size=DEFAULT_SYNTHESIS_CACHE_SIZE,
    ttl_seconds=3600,  # Longer TTL for synthesis
)


def _make_cache_key(*args, **kwargs) -> str:
    """Create a cache key from arguments."""
    key_parts = []

    for arg in args:
        if isinstance(arg, str):
            key_parts.append(arg[:100])  # Truncate long strings
        elif isinstance(arg, list | tuple):
            key_parts.append(str(sorted(arg))[:100])
        else:
            key_parts.append(str(arg)[:50])

    for k, v in sorted(kwargs.items()):
        if v is not None:
            key_parts.append(f"{k}={str(v)[:50]}")

    key_string = "|".join(key_parts)
    return hashlib.md5(key_string.encode("utf-8")).hexdigest()


def cached_vector_search(func: Callable) -> Callable:
    """
    Decorator to cache vector search results.

    Usage:
        @cached_vector_search
        def hybrid_search(question: str, ...) -> tuple:
            ...
    """

    def wrapper(question: str, *args, **kwargs):
        # Create cache key
        cache_key = _make_cache_key("vector", question, kwargs.get("allowed_sources"), kwargs.get("retrieval_strategy"))

        # Try cache first
        cached_result = _vector_search_cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"Vector search cache hit: {cache_key[:16]}")
            return cached_result

        # Execute search
        result = func(question, *args, **kwargs)

        # Cache result
        _vector_search_cache.set(cache_key, result)
        logger.debug(f"Vector search cache miss: {cache_key[:16]}")

        return result

    return wrapper


def cached_router_decision(func: Callable) -> Callable:
    """
    Decorator to cache router decisions.

    Cache key includes: question, agent_class_hint, use_reasoning, use_llm_intent,
    and cache version to prevent collisions between different routing configurations
    and calibration versions.

    Usage:
        @cached_router_decision
        def decide_route(question: str, ...) -> RouteDecision:
            ...
    """

    def wrapper(question: str, *args, **kwargs):
        # Create cache key with all relevant parameters including version
        cache_key = _make_cache_key(
            "router",
            ROUTER_CACHE_VERSION,  # Include version to invalidate on calibration changes
            question,
            kwargs.get("agent_class_hint"),
            kwargs.get("use_reasoning"),
            kwargs.get("use_llm_intent"),
        )

        # Try cache first
        cached_result = _router_decision_cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"Router decision cache hit: {cache_key[:16]}")
            return cached_result

        # Make decision
        result = func(question, *args, **kwargs)

        # Cache result
        _router_decision_cache.set(cache_key, result)
        logger.debug(f"Router decision cache miss: {cache_key[:16]}")

        return result

    return wrapper


def get_agent_cache_stats() -> dict:
    """
    Get statistics for all agent caches.

    Returns:
        Dictionary with stats for each cache
    """
    return {
        "vector_search": _vector_search_cache.stats(),
        "router_decision": _router_decision_cache.stats(),
        "synthesis": _synthesis_cache.stats(),
    }


def clear_agent_caches() -> None:
    """Clear all agent caches."""
    _vector_search_cache.clear()
    _router_decision_cache.clear()
    _synthesis_cache.clear()
    logger.info("All agent caches cleared")
