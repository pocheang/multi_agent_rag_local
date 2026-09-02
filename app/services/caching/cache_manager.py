"""Multi-level cache manager for RAG system."""

import asyncio
import hashlib
import json
import logging
import re
import time
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

# A cache namespace is a name. `clear_prefix` builds a Redis match pattern from
# it, so a caller passing `*` is asking for a different operation than the one
# the parameter names. Declared here, beside the code that builds the glob,
# rather than only at the HTTP edge: the edge is where it is convenient to
# check, and this is where it matters.
CACHE_PREFIX_PATTERN = r"^[A-Za-z0-9_-]{1,64}$"
_CACHE_PREFIX = re.compile(CACHE_PREFIX_PATTERN)


@dataclass
class CacheEntry:
    """Cache entry with metadata."""

    key: str
    value: Any
    created_at: float
    accessed_at: float
    access_count: int
    ttl: int  # seconds
    size_bytes: int = 0

    @property
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        return time.time() - self.created_at > self.ttl

    @property
    def age_seconds(self) -> float:
        """Get entry age in seconds."""
        return time.time() - self.created_at


class CacheBackend(ABC):
    """Abstract cache backend interface."""

    @abstractmethod
    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: int) -> None:
        """Set value in cache."""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete key from cache."""
        pass

    @abstractmethod
    async def clear(self) -> None:
        """Clear all cache entries."""
        pass

    @abstractmethod
    async def exists(self, key: str) -> bool:
        """Check if key exists."""
        pass


class LRUMemoryCache(CacheBackend):
    """LRU memory cache with TTL support."""

    def __init__(self, max_size: int = 256, default_ttl: int = 300):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._lock = asyncio.Lock()
        self._hits = 0
        self._misses = 0

    async def get(self, key: str) -> Any | None:
        """Get value from cache."""
        async with self._lock:
            if key not in self._cache:
                self._misses += 1
                return None

            entry = self._cache[key]

            # Check expiration
            if entry.is_expired:
                del self._cache[key]
                self._misses += 1
                return None

            # Update access metadata
            entry.accessed_at = time.time()
            entry.access_count += 1

            # Move to end (most recently used)
            self._cache.move_to_end(key)

            self._hits += 1
            return entry.value

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in cache."""
        async with self._lock:
            ttl = ttl or self.default_ttl

            # Remove oldest if at capacity
            if len(self._cache) >= self.max_size and key not in self._cache:
                self._cache.popitem(last=False)

            # Calculate size (approximate)
            size_bytes = len(str(value).encode())

            entry = CacheEntry(
                key=key,
                value=value,
                created_at=time.time(),
                accessed_at=time.time(),
                access_count=0,
                ttl=ttl,
                size_bytes=size_bytes,
            )

            self._cache[key] = entry
            self._cache.move_to_end(key)

    async def delete(self, key: str) -> None:
        """Delete key from cache."""
        async with self._lock:
            self._cache.pop(key, None)

    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    async def clear_prefix(self, prefix: str) -> None:
        """Clear entries belonging to one cache namespace."""
        key_prefix = f"{prefix}:"
        async with self._lock:
            for key in [key for key in self._cache if key.startswith(key_prefix)]:
                del self._cache[key]

    async def exists(self, key: str) -> bool:
        """Check if key exists and is not expired."""
        value = await self.get(key)
        return value is not None

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0

        return {
            "size": len(self._cache),
            "max_size": self.max_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "total_requests": total_requests,
        }


class RedisCache(CacheBackend):
    """Redis cache backend."""

    def __init__(
        self,
        redis_url: str = "redis://localhost:6379/0",
        default_ttl: int = 3600,
        namespace: str = "querymind:cache",
    ):
        self.redis_url = redis_url
        self.default_ttl = default_ttl
        self.namespace = namespace.strip(":") or "querymind:cache"
        self._client: Any | None = None

    def _key(self, key: str) -> str:
        return f"{self.namespace}:{key}"

    async def _get_client(self):
        """Get or create Redis client."""
        if self._client is None:
            try:
                import redis.asyncio as redis

                self._client = await redis.from_url(self.redis_url, encoding="utf-8", decode_responses=True)
            except ImportError:
                logger.warning("redis not installed, Redis cache disabled")
                return None
            except Exception as e:
                logger.error(f"Error connecting to Redis: {e}")
                return None
        return self._client

    async def get(self, key: str) -> Any | None:
        """Get value from Redis."""
        client = await self._get_client()
        if client is None:
            return None

        try:
            value = await client.get(self._key(key))
            if value is None:
                return None

            # Deserialize JSON
            return json.loads(value)
        except Exception as e:
            logger.error(f"Error getting from Redis: {e}")
            return None

    async def set(self, key: str, value: Any, ttl: int | None = None) -> None:
        """Set value in Redis."""
        client = await self._get_client()
        if client is None:
            return

        try:
            ttl = ttl or self.default_ttl
            # Serialize to JSON
            serialized = json.dumps(value)
            await client.setex(self._key(key), ttl, serialized)
        except Exception as e:
            logger.error(f"Error setting in Redis: {e}")

    async def delete(self, key: str) -> None:
        """Delete key from Redis."""
        client = await self._get_client()
        if client is None:
            return

        try:
            await client.delete(self._key(key))
        except Exception as e:
            logger.error(f"Error deleting from Redis: {e}")

    async def clear(self) -> None:
        """Clear only keys owned by this cache namespace."""
        client = await self._get_client()
        if client is None:
            return

        try:
            keys = [key async for key in client.scan_iter(match=f"{self.namespace}:*")]
            if keys:
                await client.delete(*keys)
        except Exception as e:
            logger.error(f"Error clearing Redis: {e}")

    async def clear_prefix(self, prefix: str) -> None:
        """Clear keys belonging to one cache namespace."""
        client = await self._get_client()
        if client is None:
            return

        try:
            keys = [key async for key in client.scan_iter(match=self._key(f"{prefix}:*"))]
            if keys:
                await client.delete(*keys)
        except Exception as e:
            logger.error(f"Error clearing Redis prefix {prefix}: {e}")

    async def exists(self, key: str) -> bool:
        """Check if key exists in Redis."""
        client = await self._get_client()
        if client is None:
            return False

        try:
            return await client.exists(self._key(key)) > 0
        except Exception as e:
            logger.error(f"Error checking existence in Redis: {e}")
            return False

    async def close(self) -> None:
        """Close Redis connection."""
        if self._client is not None:
            try:
                await self._client.aclose()
            except Exception as e:
                logger.error(f"Error closing Redis connection: {e}")
            finally:
                self._client = None


class CacheManager:
    """Multi-level cache manager with L1 (memory) and L2 (Redis) support."""

    def __init__(
        self,
        l1_max_size: int = 256,
        l1_ttl: int = 300,
        l2_enabled: bool = False,
        l2_ttl: int = 3600,
        redis_url: str | None = None,
    ):
        self.l1_cache = LRUMemoryCache(max_size=l1_max_size, default_ttl=l1_ttl)
        self.l2_cache: RedisCache | None = None
        self.l2_enabled = l2_enabled
        self.l2_ttl = l2_ttl
        self.redis_url = redis_url
        self._initialized = False

        self._l1_hits = 0
        self._l2_hits = 0
        self._misses = 0

    async def initialize(self) -> None:
        """Initialize the cache manager (async setup for Redis)."""
        if self._initialized:
            return

        if self.l2_enabled and self.redis_url:
            try:
                self.l2_cache = RedisCache(redis_url=self.redis_url, default_ttl=self.l2_ttl)
                logger.info(f"L2 Redis cache enabled: {self.redis_url}")
            except Exception as e:
                logger.warning(f"Failed to initialize Redis cache: {e}")
                self.l2_enabled = False
                self.l2_cache = None

        self._initialized = True

    async def close(self) -> None:
        """Close cache connections."""
        if self.l2_cache is not None:
            try:
                await self.l2_cache.close()
            except Exception as e:
                logger.warning(f"Error closing L2 cache: {e}")

        self._initialized = False

    def _generate_key(self, prefix: str, **kwargs) -> str:
        """Generate cache key from parameters."""
        # Sort kwargs for consistent key generation
        sorted_items = sorted(kwargs.items())
        key_str = f"{prefix}:" + ":".join(f"{k}={v}" for k, v in sorted_items)

        # Hash for shorter keys
        # A cache key, not a security primitive -- said out loud so neither a
        # reader nor a scanner has to guess which one it is.
        key_hash = hashlib.md5(key_str.encode(), usedforsecurity=False).hexdigest()
        return f"{prefix}:{key_hash}"

    async def get(self, prefix: str, default: Any = None, **kwargs) -> Any | None:
        """Get value from multi-level cache."""
        key = self._generate_key(prefix, **kwargs)

        # L1 cache (memory)
        value = await self.l1_cache.get(key)
        if value is not None:
            self._l1_hits += 1
            logger.debug(f"L1 cache hit: {prefix}")
            return value

        # L2 cache (Redis)
        if self.l2_cache:
            value = await self.l2_cache.get(key)
            if value is not None:
                self._l2_hits += 1
                logger.debug(f"L2 cache hit: {prefix}")

                # Populate L1 cache
                await self.l1_cache.set(key, value)
                return value

        self._misses += 1
        logger.debug(f"Cache miss: {prefix}")
        return default

    async def set(
        self, prefix: str, value: Any, l1_ttl: int | None = None, l2_ttl: int | None = None, **kwargs
    ) -> None:
        """Set value in multi-level cache."""
        key = self._generate_key(prefix, **kwargs)

        # Set in L1
        await self.l1_cache.set(key, value, ttl=l1_ttl)

        # Set in L2
        if self.l2_cache:
            await self.l2_cache.set(key, value, ttl=l2_ttl)

        logger.debug(f"Cache set: {prefix}")

    async def delete(self, prefix: str, **kwargs) -> None:
        """Delete from all cache levels."""
        key = self._generate_key(prefix, **kwargs)

        await self.l1_cache.delete(key)
        if self.l2_cache:
            await self.l2_cache.delete(key)

    async def clear_prefix(self, prefix: str) -> None:
        """Clear all entries in one namespace.

        Rejects anything that is not a namespace name. The Redis backend turns
        this into `scan_iter(match=f"{prefix}:*")`, so `*` would clear every
        namespace -- an operation this class already offers as `clear()`, and one
        nobody should reach by accident through the parameter that names a single
        one.
        """

        if not _CACHE_PREFIX.fullmatch(prefix or ""):
            raise ValueError(f"cache prefix must match {CACHE_PREFIX_PATTERN}")
        await self.l1_cache.clear_prefix(prefix)
        if self.l2_cache:
            await self.l2_cache.clear_prefix(prefix)

    async def clear(self) -> None:
        """Clear all caches."""
        await self.l1_cache.clear()
        if self.l2_cache:
            await self.l2_cache.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get comprehensive cache statistics."""
        l1_stats = self.l1_cache.get_stats()

        total_hits = self._l1_hits + self._l2_hits
        total_requests = total_hits + self._misses
        overall_hit_rate = total_hits / total_requests if total_requests > 0 else 0

        return {
            "l1": l1_stats,
            "l2_enabled": self.l2_cache is not None,
            "l1_hits": self._l1_hits,
            "l2_hits": self._l2_hits,
            "misses": self._misses,
            "total_requests": total_requests,
            "overall_hit_rate": overall_hit_rate,
        }
