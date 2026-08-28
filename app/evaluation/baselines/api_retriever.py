"""Evaluation-only retrieval baselines used by the HTTP evaluation adapter."""

from __future__ import annotations

import logging
import time

from app.core.config import get_settings
from app.evaluation.models import RetrievalResult
from app.retrievers.hybrid.retriever import hybrid_search_with_diagnostics
from app.retrievers.stores.vector import similarity_search

__all__ = ["SUPPORTED_SYSTEMS", "SimpleRetriever", "create_api_retriever"]

logger = logging.getLogger(__name__)

SUPPORTED_SYSTEMS = ("vector_only", "hybrid")


class SimpleRetriever:
    """Simple retriever wrapper for evaluation baselines."""

    def __init__(self, system_name: str):
        """Initialize the requested vector, hybrid, or rerank baseline."""
        self.system_name = system_name
        self.settings = get_settings()

    def retrieve(self, query: str, query_id: str = "") -> RetrievalResult:
        """Retrieve documents for one evaluation query and capture latency."""
        start_time = time.time()

        try:
            if self.system_name == "vector_only":
                results = similarity_search(
                    query=query,
                    top_k=self.settings.vector_top_k or 10,
                    allowed_sources=None,
                )
                retrieved_docs = [doc.get("source", "") for doc in results]
            elif self.system_name == "hybrid":
                results, _ = hybrid_search_with_diagnostics(
                    query=query,
                    allowed_sources=None,
                )
                retrieved_docs = [doc.get("source", "") for doc in results]
            else:
                raise ValueError(f"Unknown system: {self.system_name}")

            latency_ms = (time.time() - start_time) * 1000
            return RetrievalResult(
                query_id=query_id,
                query=query,
                retrieved_docs=retrieved_docs,
                latency_ms=latency_ms,
            )
        except Exception as exc:
            logger.error(f"Retrieval failed for query '{query}': {exc}")
            latency_ms = (time.time() - start_time) * 1000
            return RetrievalResult(query_id=query_id, query=query, retrieved_docs=[], latency_ms=latency_ms)

    def batch_retrieve(self, queries: list[tuple[str, str]]) -> list[RetrievalResult]:
        """Retrieve documents for multiple evaluation queries."""
        return [self.retrieve(query_text, query_id) for query_text, query_id in queries]


def create_api_retriever(system_name: str) -> SimpleRetriever:
    """Build a named evaluation baseline or reject an unsupported system."""
    if system_name not in SUPPORTED_SYSTEMS:
        raise ValueError(f"Unknown system: {system_name}. Available systems: {', '.join(SUPPORTED_SYSTEMS)}")
    return SimpleRetriever(system_name)
