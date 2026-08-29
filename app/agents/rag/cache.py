"""
Graph RAG caching - 使用统一的缓存后端

迁移说明:
- 之前: 自定义 LRUCache 实现
- 现在: 使用 app/services/caching/cache_manager.py 的 LRUMemoryCache
- API保持不变，确保向后兼容
"""

import hashlib
import json
import logging
from collections.abc import Callable
from typing import Any

from app.services.caching.cache_manager import LRUMemoryCache

logger = logging.getLogger(__name__)

# 默认缓存设置
DEFAULT_MAX_SIZE = 1000
DEFAULT_TTL_SECONDS = 3600  # 1 hour


def _make_content_hash(content: str) -> str:
    """
    Create a hash key from content.

    Args:
        content: Text content
    Returns:
        Hash string
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _make_document_hash(document: dict[str, Any]) -> str:
    """Hash all inputs that affect document-context analysis."""
    payload = {
        "content": str(document.get("content", "") or ""),
        "metadata": document.get("metadata", {}) or {},
    }
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


# 全局缓存实例
_pdf_quality_cache = LRUMemoryCache(max_size=500, default_ttl=3600)
_entity_extraction_cache = LRUMemoryCache(max_size=500, default_ttl=3600)
_document_context_cache = LRUMemoryCache(max_size=200, default_ttl=1800)


def cached_pdf_quality(func: Callable) -> Callable:
    """
    Decorator to cache PDF quality analysis results.

    Usage:
        @cached_pdf_quality
        def analyze_pdf_quality(text: str, metadata: dict) -> float:
            ...
    """

    def wrapper(text: str, metadata: dict) -> float:
        # Create cache key from every input used by the quality calculation.
        content_hash = _make_content_hash(text)
        metadata_str = json.dumps(metadata, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
        metadata_hash = hashlib.sha256(metadata_str.encode("utf-8")).hexdigest()
        cache_key = f"quality:{content_hash}:{metadata_hash}"

        # Try cache first (sync wrapper for async cache)
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        cached_result = loop.run_until_complete(_pdf_quality_cache.get(cache_key))
        if cached_result is not None:
            logger.debug(f"PDF quality cache hit: {cache_key[:16]}")
            return cached_result

        # Compute and cache
        result = func(text, metadata)
        loop.run_until_complete(_pdf_quality_cache.set(cache_key, result))
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
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        cached_result = loop.run_until_complete(_entity_extraction_cache.get(cache_key))
        if cached_result is not None:
            logger.debug(f"Entity extraction cache hit: {cache_key[:16]}")
            return cached_result

        # Compute and cache
        result = func(text, limit)
        loop.run_until_complete(_entity_extraction_cache.set(cache_key, result))
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
        question_hash = hashlib.sha256(question.encode("utf-8")).hexdigest()
        doc_hashes = [_make_document_hash(doc) for doc in retrieved_docs[:top_k]]
        cache_key = f"context:{question_hash}:{top_k}:{':'.join(doc_hashes)}"

        # Try cache first
        import asyncio

        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        cached_result = loop.run_until_complete(_document_context_cache.get(cache_key))
        if cached_result is not None:
            logger.debug(f"Document context cache hit: {cache_key[:16]}")
            return cached_result

        # Compute and cache
        result = func(question, retrieved_docs, top_k)
        loop.run_until_complete(_document_context_cache.set(cache_key, result))
        logger.debug(f"Document context cache miss: {cache_key[:16]}")

        return result

    return wrapper


def get_cache_stats() -> dict:
    """
    Get statistics for all caches.

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
        "pdf_quality": _pdf_quality_cache.get_stats(),
        "entity_extraction": _entity_extraction_cache.get_stats(),
        "document_context": _document_context_cache.get_stats(),
    }


def clear_all_caches() -> None:
    """Clear all Graph RAG caches."""
    import asyncio

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(_pdf_quality_cache.clear())
    loop.run_until_complete(_entity_extraction_cache.clear())
    loop.run_until_complete(_document_context_cache.clear())
    logger.info("All Graph RAG caches cleared")
