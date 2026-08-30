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
"""

import hashlib
import json
import logging
from collections.abc import Callable

from app.services.caching.cache_manager import LRUMemoryCache

logger = logging.getLogger(__name__)

# Cache configuration
DEFAULT_ROUTER_CACHE_SIZE = 500
DEFAULT_TTL_SECONDS = 1800  # 30 minutes

# Router cache version - increment when calibration logic changes
ROUTER_CACHE_VERSION = "v2_calibrated"

_router_decision_cache = LRUMemoryCache(max_size=DEFAULT_ROUTER_CACHE_SIZE, default_ttl=DEFAULT_TTL_SECONDS)


def _make_cache_key(*args, **kwargs) -> str:
    """Create a cache key from arguments."""
    payload = {
        "args": args,
        "kwargs": {key: value for key, value in sorted(kwargs.items()) if value is not None},
    }
    key_string = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(key_string.encode("utf-8")).hexdigest()


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
