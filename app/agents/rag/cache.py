"""
Simple in-memory cache for Graph RAG operations.

This module provides caching for expensive operations like:
- PDF quality analysis
- Entity extraction
- Document context analysis
"""

import hashlib
import logging
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

logger = logging.getLogger(__name__)

# Default cache settings
DEFAULT_MAX_SIZE = 1000
DEFAULT_TTL_SECONDS = 3600  # 1 hour


@dataclass
class CacheEntry:
    """Cache entry with value and metadata."""

    value: Any
    created_at: datetime
    hits: int = 0


class LRUCache:
    """
    Simple LRU cache with TTL support.

    Not thread-safe - suitable for single-process applications.
    For production with multiple workers, consider Redis.
    """

    def __init__(self, max_size: int = DEFAULT_MAX_SIZE, ttl_seconds: int = DEFAULT_TTL_SECONDS):
        """
        Initialize cache.

        Args:
            max_size: Maximum number of entries
            ttl_seconds: Time-to-live for entries in seconds
        """
        self.max_size = max_size
        self.ttl = timedelta(seconds=ttl_seconds)
        self._cache: OrderedDict[str, CacheEntry] = OrderedDict()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value if found and not expired, None otherwise
        """
        if key not in self._cache:
            self._misses += 1
            return None

        entry = self._cache[key]

        # Check expiration
        if datetime.now() - entry.created_at > self.ttl:
            logger.debug(f"Cache entry expired: {key}")
            del self._cache[key]
            self._misses += 1
            return None

        # Move to end (most recently used)
        self._cache.move_to_end(key)
        entry.hits += 1
        self._hits += 1

        return entry.value

    def set(self, key: str, value: Any) -> None:
        """
        Store value in cache.

        Args:
            key: Cache key
            value: Value to store
        """
        # Remove oldest if at capacity
        if key not in self._cache and len(self._cache) >= self.max_size:
            oldest_key = next(iter(self._cache))
            logger.debug(f"Cache full, evicting: {oldest_key}")
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
        logger.info("Cache cleared")

    def stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache stats
        """
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
_pdf_quality_cache = LRUCache(max_size=500, ttl_seconds=3600)
_entity_extraction_cache = LRUCache(max_size=500, ttl_seconds=3600)
_document_context_cache = LRUCache(max_size=200, ttl_seconds=1800)


def _make_content_hash(content: str, max_length: int = 1000) -> str:
    """
    Create a hash key from content.

    Args:
        content: Text content
        max_length: Maximum content length to hash (for performance)

    Returns:
        Hash string
    """
    # Use first N chars for performance with large documents
    sample = content[:max_length] if len(content) > max_length else content
    return hashlib.md5(sample.encode("utf-8")).hexdigest()


def cached_pdf_quality(func: Callable) -> Callable:
    """
    Decorator to cache PDF quality analysis results.

    Usage:
        @cached_pdf_quality
        def analyze_pdf_quality(text: str, metadata: dict) -> float:
            ...
    """

    def wrapper(text: str, metadata: dict) -> float:
        # Create cache key from content hash and metadata
        content_hash = _make_content_hash(text)
        metadata_str = f"{metadata.get('format', '')}{metadata.get('total_pages', '')}"
        cache_key = f"quality:{content_hash}:{metadata_str}"

        # Try cache first
        cached_result = _pdf_quality_cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"PDF quality cache hit: {cache_key[:16]}")
            return cached_result

        # Compute and cache
        result = func(text, metadata)
        _pdf_quality_cache.set(cache_key, result)
        logger.debug(f"PDF quality cache miss: {cache_key[:16]}")

        return result

    return wrapper


def cached_entity_extraction(func: Callable) -> Callable:
    """
    Decorator to cache entity extraction results.

    Usage:
        @cached_entity_extraction
        def extract_document_entities(text: str, limit: int = 20) -> list[str]:
            ...
    """

    def wrapper(text: str, limit: int = 20) -> list[str]:
        # Create cache key
        content_hash = _make_content_hash(text)
        cache_key = f"entities:{content_hash}:{limit}"

        # Try cache first
        cached_result = _entity_extraction_cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"Entity extraction cache hit: {cache_key[:16]}")
            return cached_result

        # Compute and cache
        result = func(text, limit)
        _entity_extraction_cache.set(cache_key, result)
        logger.debug(f"Entity extraction cache miss: {cache_key[:16]}")

        return result

    return wrapper


def cached_document_context(func: Callable) -> Callable:
    """
    Decorator to cache document context analysis.

    Usage:
        @cached_document_context
        def get_document_context_for_query(question: str, retrieved_docs: list[dict], top_k: int = 3) -> dict:
            ...
    """

    def wrapper(question: str, retrieved_docs: list[dict], top_k: int = 3) -> dict:
        # Create cache key from question and doc hashes
        question_hash = hashlib.md5(question.encode("utf-8")).hexdigest()[:8]
        doc_hashes = [_make_content_hash(doc.get("content", ""))[:8] for doc in retrieved_docs[:top_k]]
        cache_key = f"context:{question_hash}:{''.join(doc_hashes)}"

        # Try cache first
        cached_result = _document_context_cache.get(cache_key)
        if cached_result is not None:
            logger.debug(f"Document context cache hit: {cache_key[:16]}")
            return cached_result

        # Compute and cache
        result = func(question, retrieved_docs, top_k)
        _document_context_cache.set(cache_key, result)
        logger.debug(f"Document context cache miss: {cache_key[:16]}")

        return result

    return wrapper


def get_cache_stats() -> dict:
    """
    Get statistics for all caches.

    Returns:
        Dictionary with stats for each cache
    """
    return {
        "pdf_quality": _pdf_quality_cache.stats(),
        "entity_extraction": _entity_extraction_cache.stats(),
        "document_context": _document_context_cache.stats(),
    }


def clear_all_caches() -> None:
    """Clear all Graph RAG caches."""
    _pdf_quality_cache.clear()
    _entity_extraction_cache.clear()
    _document_context_cache.clear()
    logger.info("All Graph RAG caches cleared")
