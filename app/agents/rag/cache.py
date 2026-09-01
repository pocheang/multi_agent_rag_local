"""Memoization for the graph route's document-quality analysis.

These three caches sit in front of pure functions over text already in memory:
no I/O, no await. They used to be `LRUMemoryCache` -- an *async* cache with an
`asyncio.Lock` -- driven from synchronous callers by this pattern:

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    loop.run_until_complete(cache.get(key))

which is wrong in two directions and was harmless only because nothing reached
it. `run_graph_rag` is called from `asyncio.to_thread`, so `get_event_loop()`
raises in the worker thread and every pooled worker installs a private loop that
is never closed -- and an `asyncio.Lock` driven from several loops does not
serialize anything. On the main thread the opposite failure waits: a *running*
loop makes `run_until_complete` raise, so a future synchronous caller inside a
request would take down the graph route rather than skip a cache.

A synchronous cache for synchronous functions removes the question. It is
deliberately not shared with `app/services/caching/`: that layer exists for
values worth reaching a network for, and reusing it here is what made an
in-memory memo look like it needed an event loop.
"""

import hashlib
import json
import logging
import time
from collections import OrderedDict
from collections.abc import Callable
from threading import RLock
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_MAX_SIZE = 1000
DEFAULT_TTL_SECONDS = 3600  # 1 hour


class _SyncTTLCache:
    """LRU + TTL memo, safe to call from any thread and from inside a loop."""

    def __init__(self, max_size: int, ttl_seconds: int) -> None:
        self._entries: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._max_size = max_size
        self._ttl = ttl_seconds
        self._lock = RLock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Any | None:
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                self._misses += 1
                return None
            expires_at, value = entry
            if expires_at <= time.monotonic():
                del self._entries[key]
                self._misses += 1
                return None
            self._entries.move_to_end(key)
            self._hits += 1
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            if key not in self._entries and len(self._entries) >= self._max_size:
                self._entries.popitem(last=False)
            self._entries[key] = (time.monotonic() + self._ttl, value)
            self._entries.move_to_end(key)

    def clear(self) -> None:
        with self._lock:
            self._entries.clear()
            self._hits = 0
            self._misses = 0

    def get_stats(self) -> dict[str, Any]:
        with self._lock:
            total = self._hits + self._misses
            return {
                "size": len(self._entries),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": self._hits / total if total else 0,
                "total_requests": total,
            }


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


_pdf_quality_cache = _SyncTTLCache(max_size=500, ttl_seconds=3600)
_entity_extraction_cache = _SyncTTLCache(max_size=500, ttl_seconds=3600)
_document_context_cache = _SyncTTLCache(max_size=200, ttl_seconds=1800)


def cached_pdf_quality(func: Callable) -> Callable:
    """
    Decorator to cache PDF quality analysis results.

    Usage:
        @cached_pdf_quality
        def analyze_pdf_quality(text: str, metadata: dict) -> float:
            ...
    """

    def wrapper(text: str, metadata: dict) -> float:
        # Every input the quality calculation reads has to be in the key: it
        # scores the text *and* the page/format metadata, so keying on the text
        # alone would serve one document's score for another's.
        content_hash = _make_content_hash(text)
        metadata_str = json.dumps(metadata, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
        metadata_hash = hashlib.sha256(metadata_str.encode("utf-8")).hexdigest()
        cache_key = f"quality:{content_hash}:{metadata_hash}"

        cached_result = _pdf_quality_cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        result = func(text, metadata)
        _pdf_quality_cache.set(cache_key, result)
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
        cache_key = f"entities:{_make_content_hash(text)}:{limit}"

        cached_result = _entity_extraction_cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        result = func(text, limit)
        _entity_extraction_cache.set(cache_key, result)
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
        question_hash = hashlib.sha256(question.encode("utf-8")).hexdigest()
        doc_hashes = [_make_document_hash(doc) for doc in retrieved_docs[:top_k]]
        cache_key = f"context:{question_hash}:{top_k}:{':'.join(doc_hashes)}"

        cached_result = _document_context_cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        result = func(question, retrieved_docs, top_k)
        _document_context_cache.set(cache_key, result)
        return result

    return wrapper


def get_cache_stats() -> dict:
    """
    Get statistics for all caches.

    Returns:
        Dictionary with stats for each cache
    """
    return {
        "pdf_quality": _pdf_quality_cache.get_stats(),
        "entity_extraction": _entity_extraction_cache.get_stats(),
        "document_context": _document_context_cache.get_stats(),
    }


def clear_all_caches() -> None:
    """Clear all Graph RAG caches."""
    _pdf_quality_cache.clear()
    _entity_extraction_cache.clear()
    _document_context_cache.clear()
    logger.info("All Graph RAG caches cleared")
