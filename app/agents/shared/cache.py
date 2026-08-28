"""
Shared caching utilities - 使用统一的缓存后端

迁移说明:
- 之前: 自定义 SimpleCache 实现
- 现在: 使用 app/services/caching/cache_manager.py 的 LRUMemoryCache
- API保持不变，确保向后兼容

Cache versioning: Router cache includes version to support calibration updates.
"""

import hashlib
import json
import logging
from collections.abc import Callable

from app.services.caching.cache_manager import LRUMemoryCache

logger = logging.getLogger(__name__)

# Cache configuration
DEFAULT_VECTOR_CACHE_SIZE = 200
DEFAULT_ROUTER_CACHE_SIZE = 500
DEFAULT_SYNTHESIS_CACHE_SIZE = 100
DEFAULT_TTL_SECONDS = 1800  # 30 minutes

# Router cache version - increment when calibration logic changes
ROUTER_CACHE_VERSION = "v2_calibrated"

# 全局缓存实例
_vector_search_cache = LRUMemoryCache(max_size=DEFAULT_VECTOR_CACHE_SIZE, default_ttl=DEFAULT_TTL_SECONDS)

_router_decision_cache = LRUMemoryCache(max_size=DEFAULT_ROUTER_CACHE_SIZE, default_ttl=DEFAULT_TTL_SECONDS)

_synthesis_cache = LRUMemoryCache(
    max_size=DEFAULT_SYNTHESIS_CACHE_SIZE,
    default_ttl=3600,  # Longer TTL for synthesis
)


def _make_cache_key(*args, **kwargs) -> str:
    """Create a cache key from arguments."""
    payload = {
        "args": args,
        "kwargs": {key: value for key, value in sorted(kwargs.items()) if value is not None},
    }
    key_string = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(key_string.encode("utf-8")).hexdigest()


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
        cache_key = _make_cache_key("vector", question, kwargs.get("allowed_sources"))

        # Try cache first
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        cached_result = loop.run_until_complete(_vector_search_cache.get(cache_key))
        if cached_result is not None:
            logger.debug(f"Vector search cache hit: {cache_key[:16]}")
            return cached_result

        # Execute search
        result = func(question, *args, **kwargs)

        # Cache result
        loop.run_until_complete(_vector_search_cache.set(cache_key, result))
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
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        cached_result = loop.run_until_complete(_router_decision_cache.get(cache_key))
        if cached_result is not None:
            logger.debug(f"Router decision cache hit: {cache_key[:16]}")
            return cached_result

        # Make decision
        result = func(question, *args, **kwargs)

        # Cache result
        loop.run_until_complete(_router_decision_cache.set(cache_key, result))
        logger.debug(f"Router decision cache miss: {cache_key[:16]}")

        return result

    return wrapper


def get_agent_cache_stats() -> dict:
    """
    Get statistics for all agent caches.

    Returns:
        Dictionary with stats for each cache
    """
    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    # LRUMemoryCache.get_stats() is synchronous
    return {
        "vector_search": _vector_search_cache.get_stats(),
        "router_decision": _router_decision_cache.get_stats(),
        "synthesis": _synthesis_cache.get_stats(),
    }


def clear_agent_caches() -> None:
    """Clear all agent caches."""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(_vector_search_cache.clear())
    loop.run_until_complete(_router_decision_cache.clear())
    loop.run_until_complete(_synthesis_cache.clear())
    logger.info("All agent caches cleared")
