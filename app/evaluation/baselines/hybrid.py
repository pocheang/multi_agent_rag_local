"""Hybrid baseline retriever (Vector + BM25)."""

import time
from typing import Any

from app.evaluation.models import RetrievalResult
from app.retrievers.bm25_retriever import bm25_search
from app.retrievers.stores.vector import similarity_search


class HybridRetriever:
    """Hybrid search baseline using vector + BM25 with score fusion."""

    def __init__(self, vector_weight: float = 0.7, bm25_weight: float = 0.3):
        """
        Initialize hybrid retriever.

        Args:
            vector_weight: Weight for vector scores (default 0.7)
            bm25_weight: Weight for BM25 scores (default 0.3)
        """
        self.vector_weight = vector_weight
        self.bm25_weight = bm25_weight

    def retrieve(self, query: str, top_k: int = 5) -> RetrievalResult:
        """
        Retrieve documents using hybrid search (vector + BM25).

        Args:
            query: Query text
            top_k: Number of documents to retrieve

        Returns:
            RetrievalResult with retrieved documents and metadata
        """
        start_time = time.time()

        # Retrieve from both sources (get more candidates for fusion)
        vector_results = similarity_search(query, k=top_k * 2)
        bm25_results = bm25_search(query, k=top_k * 2)

        # Normalize and fuse scores
        fused_scores = self._fuse_scores(vector_results, bm25_results)

        # Sort by fused score and take top_k
        sorted_results = sorted(fused_scores.items(), key=lambda x: x[1]["score"], reverse=True)[:top_k]

        latency_ms = (time.time() - start_time) * 1000

        # Format results
        retrieved_docs = []
        scores = []

        for _doc_id, data in sorted_results:
            retrieved_docs.append(
                {
                    "id": data["doc"].metadata.get("id", ""),
                    "content": data["doc"].page_content,
                    "metadata": data["doc"].metadata,
                    "source": data["doc"].metadata.get("source", ""),
                }
            )
            scores.append(float(data["score"]))

        return RetrievalResult(
            query_id="",  # Will be set by evaluation service
            query=query,
            retrieved_docs=retrieved_docs,
            scores=scores,
            latency_ms=latency_ms,
            metadata={
                "retriever": "hybrid",
                "vector_weight": self.vector_weight,
                "bm25_weight": self.bm25_weight,
                "top_k": top_k,
            },
        )

    def _fuse_scores(self, vector_results: list[tuple], bm25_results: list[tuple]) -> dict[str, dict[str, Any]]:
        """
        Fuse vector and BM25 scores using weighted average.

        Args:
            vector_results: List of (doc, score) tuples from vector search
            bm25_results: List of (doc, score) tuples from BM25 search

        Returns:
            Dictionary mapping doc_id to {doc, score, vector_score, bm25_score}
        """
        fused = {}

        # Normalize vector scores (0-1 range)
        if vector_results:
            max_vector_score = max(score for _, score in vector_results)
            min_vector_score = min(score for _, score in vector_results)
            vector_range = max_vector_score - min_vector_score
            if vector_range == 0:
                vector_range = 1.0

            for doc, score in vector_results:
                doc_id = doc.metadata.get("id", doc.page_content[:50])
                normalized_score = (score - min_vector_score) / vector_range
                fused[doc_id] = {
                    "doc": doc,
                    "vector_score": normalized_score,
                    "bm25_score": 0.0,
                    "score": normalized_score * self.vector_weight,
                }

        # Normalize BM25 scores (0-1 range)
        if bm25_results:
            max_bm25_score = max(score for _, score in bm25_results)
            min_bm25_score = min(score for _, score in bm25_results)
            bm25_range = max_bm25_score - min_bm25_score
            if bm25_range == 0:
                bm25_range = 1.0

            for doc, score in bm25_results:
                doc_id = doc.metadata.get("id", doc.page_content[:50])
                normalized_score = (score - min_bm25_score) / bm25_range

                if doc_id in fused:
                    # Update existing entry
                    fused[doc_id]["bm25_score"] = normalized_score
                    fused[doc_id]["score"] += normalized_score * self.bm25_weight
                else:
                    # New entry from BM25 only
                    fused[doc_id] = {
                        "doc": doc,
                        "vector_score": 0.0,
                        "bm25_score": normalized_score,
                        "score": normalized_score * self.bm25_weight,
                    }

        return fused
