"""Compatibility re-export for app.agents.rag.cache; implementation lives in the canonical package."""

from app.agents.rag.cache import (
    DEFAULT_MAX_SIZE,
    DEFAULT_TTL_SECONDS,
    CacheEntry,
    LRUCache,
    cached_document_context,
    cached_entity_extraction,
    cached_pdf_quality,
    clear_all_caches,
    get_cache_stats,
)

__all__ = [
    "DEFAULT_MAX_SIZE",
    "DEFAULT_TTL_SECONDS",
    "CacheEntry",
    "LRUCache",
    "cached_pdf_quality",
    "cached_entity_extraction",
    "cached_document_context",
    "get_cache_stats",
    "clear_all_caches",
]
