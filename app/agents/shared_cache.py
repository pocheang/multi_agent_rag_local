"""Compatibility re-export for app.agents.shared.cache; implementation lives in the canonical package."""

from app.agents.shared.cache import (
    DEFAULT_ROUTER_CACHE_SIZE,
    DEFAULT_SYNTHESIS_CACHE_SIZE,
    DEFAULT_TTL_SECONDS,
    DEFAULT_VECTOR_CACHE_SIZE,
    ROUTER_CACHE_VERSION,
    CacheEntry,
    SimpleCache,
    cached_router_decision,
    cached_vector_search,
    clear_agent_caches,
    get_agent_cache_stats,
)

__all__ = [
    "DEFAULT_VECTOR_CACHE_SIZE",
    "DEFAULT_ROUTER_CACHE_SIZE",
    "DEFAULT_SYNTHESIS_CACHE_SIZE",
    "DEFAULT_TTL_SECONDS",
    "ROUTER_CACHE_VERSION",
    "CacheEntry",
    "SimpleCache",
    "cached_vector_search",
    "cached_router_decision",
    "get_agent_cache_stats",
    "clear_agent_caches",
]
