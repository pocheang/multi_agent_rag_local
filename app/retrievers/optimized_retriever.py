"""Optimized hybrid retriever with caching and batch processing."""

import asyncio
import logging
from typing import Any

from app.core.config import get_settings
from app.retrievers.hybrid.retriever import HybridRetriever
from app.services.caching.cache_manager import CacheManager
from app.services.caching.semantic_cache import SemanticCache
from app.services.performance.monitor import get_monitor

logger = logging.getLogger(__name__)


class OptimizedHybridRetriever:
    """Optimized hybrid retriever with caching and performance enhancements."""

    def __init__(
        self,
        enable_cache: bool = True,
        enable_semantic_cache: bool = True,
        batch_size: int = 10,
    ):
        self.settings = get_settings()
        self.base_retriever = HybridRetriever()
        self.enable_cache = enable_cache
        self.enable_semantic_cache = enable_semantic_cache
        self.batch_size = batch_size
        self.monitor = get_monitor()

        # Initialize caching
        if self.enable_cache:
            self.cache_manager = CacheManager(
                l1_max_size=256,
                l1_ttl=300,  # 5 minutes
                l2_enabled=getattr(self.settings, "cache_l2_enabled", False),
                l2_ttl=3600,  # 1 hour
            )

            if self.enable_semantic_cache:
                self.semantic_cache = SemanticCache(
                    cache_manager=self.cache_manager,
                    similarity_threshold=0.95,
                )
        else:
            self.cache_manager = None
            self.semantic_cache = None

    async def retrieve(
        self,
        query: str,
        top_k: int = 10,
        **kwargs: Any,
    ) -> list[dict[str, Any]]:
        """Retrieve documents with caching and optimization.

        Args:
            query: Search query
            top_k: Number of results to return
            **kwargs: Additional retrieval parameters

        Returns:
            List of retrieved documents
        """
        async with self.monitor.measure_async("retrieval_total"):
            # Try cache first
            if self.cache_manager:
                cached_result = await self._get_from_cache(query, top_k, **kwargs)
                if cached_result is not None:
                    self.monitor.increment_counter("retrieval_cache_hits")
                    return cached_result

                self.monitor.increment_counter("retrieval_cache_misses")

            # Perform retrieval
            async with self.monitor.measure_async("retrieval_execution"):
                results = await self.base_retriever.retrieve(query, top_k=top_k, **kwargs)

            # Cache results
            if self.cache_manager:
                await self._set_to_cache(query, results, top_k, **kwargs)

            return results

    async def retrieve_batch(
        self,
        queries: list[str],
        top_k: int = 10,
        **kwargs: Any,
    ) -> list[list[dict[str, Any]]]:
        """Batch retrieve with automatic batching and deduplication.

        Args:
            queries: List of search queries
            top_k: Number of results per query
            **kwargs: Additional retrieval parameters

        Returns:
            List of result lists (one per query)
        """
        async with self.monitor.measure_async("retrieval_batch"):
            # Deduplicate queries
            unique_queries = list(dict.fromkeys(queries))
            {q: i for i, q in enumerate(unique_queries)}

            # Process in batches
            all_results: dict[str, list[dict[str, Any]]] = {}

            for i in range(0, len(unique_queries), self.batch_size):
                batch = unique_queries[i : i + self.batch_size]

                # Retrieve batch concurrently
                batch_tasks = [self.retrieve(query, top_k=top_k, **kwargs) for query in batch]
                batch_results = await asyncio.gather(*batch_tasks)

                # Store results
                for query, result in zip(batch, batch_results, strict=False):
                    all_results[query] = result

            # Map back to original order (with duplicates)
            ordered_results = [all_results[q] for q in queries]

            self.monitor.set_gauge(
                "retrieval_batch_dedup_ratio",
                len(unique_queries) / len(queries) if queries else 1.0,
            )

            return ordered_results

    async def _get_from_cache(self, query: str, top_k: int, **kwargs: Any) -> list[dict[str, Any]] | None:
        """Get results from cache."""
        cache_key_params = {"query": query, "top_k": top_k, **kwargs}

        if self.semantic_cache:
            # Try semantic cache (needs embedding)
            try:
                query_embedding = await self._get_query_embedding(query)
                result = await self.semantic_cache.get_similar(query, query_embedding, prefix="retrieval")
                if result is not None:
                    logger.debug(f"Semantic cache hit for: {query[:50]}")
                    return result
            except Exception as e:
                logger.warning(f"Semantic cache error: {e}")

        # Fall back to regular cache
        return await self.cache_manager.get("retrieval", **cache_key_params)

    async def _set_to_cache(self, query: str, results: list[dict[str, Any]], top_k: int, **kwargs: Any) -> None:
        """Set results to cache."""
        cache_key_params = {"query": query, "top_k": top_k, **kwargs}

        if self.semantic_cache:
            # Set with semantic cache
            try:
                query_embedding = await self._get_query_embedding(query)
                await self.semantic_cache.set_with_embedding(
                    query, query_embedding, results, prefix="retrieval", ttl=300
                )
                return
            except Exception as e:
                logger.warning(f"Semantic cache set error: {e}")

        # Fall back to regular cache
        await self.cache_manager.set("retrieval", results, l1_ttl=300, l2_ttl=3600, **cache_key_params)

    async def _get_query_embedding(self, query: str) -> Any:
        """Get query embedding with caching."""
        if not self.cache_manager:
            return await self._compute_embedding(query)

        # Check embedding cache
        cached_embedding = await self.cache_manager.get("embedding", query=query)
        if cached_embedding is not None:
            return cached_embedding

        # Compute and cache
        embedding = await self._compute_embedding(query)
        await self.cache_manager.set("embedding", embedding, l1_ttl=600, l2_ttl=3600, query=query)

        return embedding

    async def _compute_embedding(self, query: str) -> Any:
        """Compute query embedding."""
        # This would call the actual embedding model
        # For now, return a placeholder
        import numpy as np

        return np.random.rand(768)  # Placeholder embedding

    def get_stats(self) -> dict[str, Any]:
        """Get retriever statistics."""
        stats = {
            "cache_enabled": self.enable_cache,
            "semantic_cache_enabled": self.enable_semantic_cache,
            "batch_size": self.batch_size,
        }

        if self.cache_manager:
            stats["cache"] = self.cache_manager.get_stats()

        if self.semantic_cache:
            stats["semantic_cache"] = self.semantic_cache.get_stats()

        return stats
