"""Cache manager initialization and lifecycle management."""

import logging

from app.services.caching.cache_manager import CacheManager

logger = logging.getLogger(__name__)

_cache_manager_instance: CacheManager | None = None


async def initialize_cache_manager(
    l1_max_size: int = 256,
    l1_ttl: int = 300,
    l2_enabled: bool = False,
    l2_ttl: int = 3600,
    redis_url: str | None = None,
) -> None:
    """Initialize the global cache manager.

    Args:
        l1_max_size: Maximum number of items in L1 cache
        l1_ttl: L1 cache TTL in seconds
        l2_enabled: Whether to enable L2 (Redis) cache
        l2_ttl: L2 cache TTL in seconds
        redis_url: Redis connection URL
    """
    global _cache_manager_instance

    if _cache_manager_instance is not None:
        logger.warning("Cache manager already initialized")
        return

    _cache_manager_instance = CacheManager(
        l1_max_size=l1_max_size,
        l1_ttl=l1_ttl,
        l2_enabled=l2_enabled,
        l2_ttl=l2_ttl,
        redis_url=redis_url,
    )

    await _cache_manager_instance.initialize()
    logger.info(f"Cache manager initialized: L1={l1_max_size}, L2={'enabled' if l2_enabled else 'disabled'}")


async def close_cache_manager() -> None:
    """Close the global cache manager."""
    global _cache_manager_instance

    if _cache_manager_instance is None:
        return

    await _cache_manager_instance.close()
    _cache_manager_instance = None
    logger.info("Cache manager closed")


def get_cache_manager() -> CacheManager:
    """Get the global cache manager instance.

    Returns:
        CacheManager instance

    Raises:
        RuntimeError: If cache manager is not initialized
    """
    if _cache_manager_instance is None:
        raise RuntimeError("Cache manager not initialized. Call initialize_cache_manager() first.")

    return _cache_manager_instance


__all__ = ["initialize_cache_manager", "close_cache_manager", "get_cache_manager"]
