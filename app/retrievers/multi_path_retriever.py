"""
Multi-path retriever for v0.4.4 accuracy improvements.

Implements fast 3-path parallel retrieval strategy:
- Path 1: Dense vector retrieval
- Path 2: BM25 sparse retrieval
- Path 3: Hybrid RRF retrieval

Target: 85-90% recall in 300ms with parallel execution.
"""

import asyncio
import logging
import time

from app.core.config import get_settings
from app.retrievers.bm25_retriever import bm25_search
from app.retrievers.hybrid.fusion import reciprocal_rank_fusion
from app.retrievers.vector_store import similarity_search
from app.services.tracing import traced_span

logger = logging.getLogger(__name__)


class MultiPathRetriever:
    """
    Multi-path retrieval with 3 parallel paths for optimal speed/accuracy balance.

    Performance targets:
    - Total retrieval time: ~300ms (parallel execution)
    - Recall@50: 85-90%
    - 3 paths cover different retrieval strategies
    """

    def __init__(self):
        self.settings = get_settings()

    async def retrieve(
        self,
        query: str,
        top_k: int = 50,
        allowed_sources: list[str] | None = None,
        enable_path1: bool = True,  # Dense vector
        enable_path2: bool = True,  # BM25 sparse
        enable_path3: bool = True,  # Hybrid RRF
    ) -> tuple[list[dict], dict]:
        """
        Execute 3-path parallel retrieval.

        Args:
            query: Search query
            top_k: Number of results to return
            allowed_sources: Optional source filter
            enable_path1: Enable dense vector retrieval
            enable_path2: Enable BM25 sparse retrieval
            enable_path3: Enable hybrid RRF retrieval

        Returns:
            Tuple of (merged results, diagnostics)
        """
        start_time = time.time()

        with traced_span("retrieval.multi_path", {"top_k": top_k}):
            # Execute all paths in parallel
            tasks = []
            path_names = []

            if enable_path1:
                tasks.append(self._path1_dense_vector(query, k=30, allowed_sources=allowed_sources))
                path_names.append("dense_vector")

            if enable_path2:
                tasks.append(self._path2_bm25_sparse(query, k=30, allowed_sources=allowed_sources))
                path_names.append("bm25_sparse")

            if enable_path3:
                tasks.append(self._path3_hybrid_rrf(query, k=20, allowed_sources=allowed_sources))
                path_names.append("hybrid_rrf")

            # Wait for all paths to complete (parallel execution)
            path_results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results and handle errors
            all_docs = []
            path_timings = {}

            for _i, (path_name, result) in enumerate(zip(path_names, path_results, strict=False)):
                if isinstance(result, Exception):
                    logger.warning(f"Path {path_name} failed: {result}")
                    path_timings[path_name] = {"status": "error", "error": str(result)}
                else:
                    docs, timing = result
                    all_docs.extend(self._tag_docs(docs, path_name))
                    path_timings[path_name] = timing

            # Fast deduplication and merging (O(n) with hash map)
            unique_docs = self._fast_deduplicate(all_docs)

            # Score by path frequency (documents appearing in multiple paths get boost)
            scored_docs = self._score_by_path_frequency(unique_docs)

            # Return top_k results
            final_results = scored_docs[:top_k]

            total_time = time.time() - start_time

            diagnostics = {
                "total_time_ms": round(total_time * 1000, 2),
                "paths_executed": path_names,
                "path_timings": path_timings,
                "total_candidates": len(all_docs),
                "unique_candidates": len(unique_docs),
                "final_results": len(final_results),
                "strategy": "fast_3_path_parallel",
            }

            logger.info(
                f"Multi-path retrieval completed in {diagnostics['total_time_ms']}ms: "
                f"{len(all_docs)} total → {len(unique_docs)} unique → {len(final_results)} final"
            )

            return final_results, diagnostics

    async def _path1_dense_vector(
        self, query: str, k: int = 30, allowed_sources: list[str] | None = None
    ) -> tuple[list[dict], dict]:
        """
        Path 1: Dense vector retrieval using embeddings.
        Target: ~200ms, 70% recall
        """
        start = time.time()

        try:
            with traced_span("retrieval.path1_dense_vector", {"k": k}):
                # Use existing vector search
                if allowed_sources:
                    try:
                        results = similarity_search(query, k=k, allowed_sources=allowed_sources)
                    except TypeError:
                        # Fallback if allowed_sources not supported
                        results = similarity_search(query, k=k, require_source_filter=False)
                else:
                    results = similarity_search(query, k=k, require_source_filter=False)

                elapsed = (time.time() - start) * 1000

                return results, {
                    "status": "success",
                    "time_ms": round(elapsed, 2),
                    "results_count": len(results),
                }

        except Exception as e:
            logger.error(f"Dense vector retrieval failed: {e}")
            elapsed = (time.time() - start) * 1000
            return [], {
                "status": "error",
                "time_ms": round(elapsed, 2),
                "error": str(e),
            }

    async def _path2_bm25_sparse(
        self, query: str, k: int = 30, allowed_sources: list[str] | None = None
    ) -> tuple[list[dict], dict]:
        """
        Path 2: BM25 sparse retrieval for keyword matching.
        Target: ~100ms, supplements vector with exact matches
        """
        start = time.time()

        try:
            with traced_span("retrieval.path2_bm25_sparse", {"k": k}):
                # Use existing BM25 search
                results = bm25_search(query, k=k, allowed_sources=allowed_sources)

                elapsed = (time.time() - start) * 1000

                return results, {
                    "status": "success",
                    "time_ms": round(elapsed, 2),
                    "results_count": len(results),
                }

        except Exception as e:
            logger.error(f"BM25 sparse retrieval failed: {e}")
            elapsed = (time.time() - start) * 1000
            return [], {
                "status": "error",
                "time_ms": round(elapsed, 2),
                "error": str(e),
            }

    async def _path3_hybrid_rrf(
        self, query: str, k: int = 20, allowed_sources: list[str] | None = None
    ) -> tuple[list[dict], dict]:
        """
        Path 3: Hybrid retrieval with RRF fusion.
        Target: ~150ms, combines strengths of both approaches
        """
        start = time.time()

        try:
            with traced_span("retrieval.path3_hybrid_rrf", {"k": k}):
                # Execute vector and BM25 in parallel for fusion
                vector_task = self._path1_dense_vector(query, k=k, allowed_sources=allowed_sources)
                bm25_task = self._path2_bm25_sparse(query, k=k, allowed_sources=allowed_sources)

                (vector_docs, _), (bm25_docs, _) = await asyncio.gather(vector_task, bm25_task)

                # Apply RRF fusion
                fused = reciprocal_rank_fusion(
                    vector_docs,
                    bm25_docs,
                    k=self.settings.hybrid_rrf_k if hasattr(self.settings, "hybrid_rrf_k") else 60,
                )

                # Return top k after fusion
                results = fused[:k]

                elapsed = (time.time() - start) * 1000

                return results, {
                    "status": "success",
                    "time_ms": round(elapsed, 2),
                    "results_count": len(results),
                    "vector_count": len(vector_docs),
                    "bm25_count": len(bm25_docs),
                }

        except Exception as e:
            logger.error(f"Hybrid RRF retrieval failed: {e}")
            elapsed = (time.time() - start) * 1000
            return [], {
                "status": "error",
                "time_ms": round(elapsed, 2),
                "error": str(e),
            }

    def _tag_docs(self, docs: list[dict], path: str) -> list[dict]:
        """Add path metadata to documents."""
        tagged = []
        for doc in docs:
            tagged_doc = dict(doc)
            tagged_doc["retrieval_path"] = path
            tagged.append(tagged_doc)
        return tagged

    def _fast_deduplicate(self, docs: list[dict]) -> list[dict]:
        """
        Fast O(n) deduplication using hash map.
        Merge documents with same ID, tracking all paths.
        """
        doc_map = {}

        for doc in docs:
            # Create unique document ID
            doc_id = self._get_doc_id(doc)

            if doc_id not in doc_map:
                # First occurrence
                doc_map[doc_id] = {
                    **doc,
                    "retrieval_paths": [doc.get("retrieval_path")],
                    "path_count": 1,
                }
            else:
                # Document already seen, merge paths
                existing = doc_map[doc_id]
                existing["retrieval_paths"].append(doc.get("retrieval_path"))
                existing["path_count"] += 1

                # Keep highest score
                current_score = doc.get("score", 0)
                existing_score = existing.get("score", 0)
                if current_score > existing_score:
                    existing["score"] = current_score

        return list(doc_map.values())

    def _get_doc_id(self, doc: dict) -> str:
        """Generate unique document ID for deduplication."""
        # Use source path + chunk index as unique identifier
        metadata = doc.get("metadata", {})
        source = metadata.get("source", "")
        chunk_idx = metadata.get("chunk_index", "")

        # Fallback to text hash if metadata not available
        if not source:
            text = doc.get("text", "")
            return f"text_{hash(text)}"

        return f"{source}_{chunk_idx}"

    def _score_by_path_frequency(self, docs: list[dict]) -> list[dict]:
        """
        Score documents based on path frequency.
        Documents appearing in multiple paths get higher scores.
        """
        for doc in docs:
            path_count = doc.get("path_count", 1)
            original_score = doc.get("score", 0.5)

            # Boost formula: score * (1 + 0.2 * (path_count - 1))
            # - 1 path: no boost (1.0x)
            # - 2 paths: 1.2x boost
            # - 3 paths: 1.4x boost
            boost_factor = 1 + 0.2 * (path_count - 1)

            doc["multi_path_score"] = original_score * boost_factor
            doc["path_boost_factor"] = boost_factor

        # Sort by multi-path score
        return sorted(docs, key=lambda x: x.get("multi_path_score", 0), reverse=True)


# Convenience function for direct usage
async def multi_path_retrieve(
    query: str, top_k: int = 50, allowed_sources: list[str] | None = None
) -> tuple[list[dict], dict]:
    """
    Convenience function for multi-path retrieval.

    Args:
        query: Search query
        top_k: Number of results to return
        allowed_sources: Optional source filter

    Returns:
        Tuple of (results, diagnostics)
    """
    retriever = MultiPathRetriever()
    return await retriever.retrieve(query, top_k, allowed_sources)
