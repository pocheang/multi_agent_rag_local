"""Semantic cache for similar queries."""

import asyncio
import logging
from typing import Any

import numpy as np

from app.services.caching.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class SemanticCache:
    """Cache that matches semantically similar queries."""

    def __init__(
        self,
        cache_manager: CacheManager,
        similarity_threshold: float = 0.95,
        max_candidates: int = 50,
    ):
        self.cache_manager = cache_manager
        self.similarity_threshold = similarity_threshold
        self.max_candidates = max_candidates
        self._embeddings_cache: dict[str, np.ndarray] = {}
        self._lock = asyncio.Lock()

    async def get_similar(
        self,
        query: str,
        query_embedding: np.ndarray,
        prefix: str = "query",
    ) -> Any | None:
        """Get cached result for semantically similar query.

        Args:
            query: Query text
            query_embedding: Query embedding vector
            prefix: Cache prefix

        Returns:
            Cached result if similar query found, None otherwise
        """
        # First try exact match
        exact_result = await self.cache_manager.get(prefix, query=query)
        if exact_result is not None:
            logger.debug(f"Exact semantic cache hit for: {query[:50]}")
            return exact_result

        # Search for similar queries
        async with self._lock:
            if not self._embeddings_cache:
                return None

            # Calculate similarities
            similarities = {}
            for cached_query, cached_embedding in self._embeddings_cache.items():
                similarity = self._cosine_similarity(query_embedding, cached_embedding)
                if similarity >= self.similarity_threshold:
                    similarities[cached_query] = similarity

            if not similarities:
                return None

            # Get most similar
            most_similar_query = max(similarities.items(), key=lambda x: x[1])[0]
            similarity_score = similarities[most_similar_query]

            # Retrieve cached result
            result = await self.cache_manager.get(prefix, query=most_similar_query)

            if result is not None:
                logger.info(
                    f"Semantic cache hit (similarity={similarity_score:.3f}): {query[:50]} ~= {most_similar_query[:50]}"
                )
                return result

        return None

    async def set_with_embedding(
        self,
        query: str,
        query_embedding: np.ndarray,
        result: Any,
        prefix: str = "query",
        ttl: int | None = None,
    ) -> None:
        """Cache result with query embedding.

        Args:
            query: Query text
            query_embedding: Query embedding vector
            result: Result to cache
            prefix: Cache prefix
            ttl: Time to live in seconds
        """
        # Store result in cache
        await self.cache_manager.set(prefix, result, l1_ttl=ttl, query=query)

        # Store embedding for similarity search
        async with self._lock:
            self._embeddings_cache[query] = query_embedding

            # Limit cache size
            if len(self._embeddings_cache) > self.max_candidates:
                # Remove oldest (simple FIFO, could use LRU)
                oldest_query = next(iter(self._embeddings_cache))
                del self._embeddings_cache[oldest_query]

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two vectors."""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)

        if norm1 == 0 or norm2 == 0:
            return 0.0

        return float(dot_product / (norm1 * norm2))

    async def clear(self) -> None:
        """Clear semantic cache."""
        async with self._lock:
            self._embeddings_cache.clear()

    def get_stats(self) -> dict[str, Any]:
        """Get semantic cache statistics."""
        return {
            "embeddings_cached": len(self._embeddings_cache),
            "max_candidates": self.max_candidates,
            "similarity_threshold": self.similarity_threshold,
        }
