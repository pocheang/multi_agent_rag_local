"""Evaluation-only retrieval baselines used by the HTTP evaluation adapter."""

from __future__ import annotations

import logging
import time
from typing import Literal, get_args

from app.core.config import get_settings
from app.evaluation.models import RetrievalResult
from app.retrievers.hybrid.retriever import hybrid_search_with_diagnostics
from app.retrievers.stores.vector import similarity_search

__all__ = ["SUPPORTED_SYSTEMS", "SimpleRetriever", "SystemName", "create_api_retriever"]

logger = logging.getLogger(__name__)

# One definition, two shapes. The type is the source of truth and the tuple is
# derived from it, so a baseline cannot be accepted by the API without being
# declared here, nor declared here without the API accepting it. The API used to
# take a bare `str`, which meant an unknown name travelled as far as
# `create_api_retriever` before being rejected -- and was logged on the way.
SystemName = Literal["vector_only", "hybrid"]
SUPPORTED_SYSTEMS: tuple[SystemName, ...] = get_args(SystemName)


def _result(query_id: str, query: str, retrieved_docs: list[str], start_time: float) -> RetrievalResult:
    """Build the one result shape both the success and the failure path return.

    There used to be two constructions, and both passed `query=` where the field
    is `query_text` -- so `RetrievalResult` raised for a missing required field on
    every query, for both baselines, and `POST /api/evaluation/run` could not
    complete. It survived because the happy path's ValidationError was swallowed
    by the bare `except Exception` below, which then re-made the identical mistake
    *outside* the try, where nothing could catch it.

    Two call sites that must agree is what let that happen, so there is one now.
    Same reasoning as the `k`/`top_k` note below: the harness is off the request
    path, so nothing exercises it until someone runs it.
    """

    return RetrievalResult(
        query_id=query_id,
        query_text=query,
        retrieved_docs=retrieved_docs,
        latency_ms=(time.time() - start_time) * 1000,
    )


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
                    # `k`, not `top_k`: this raised TypeError on every call, so
                    # the vector_only baseline had never once run. The unfiltered
                    # search is the point here -- the harness measures retrieval
                    # over a fixed corpus with no request and no user -- and is
                    # allowlisted in tests/security/test_no_unrestricted_retrieval.py.
                    k=self.settings.vector_top_k or 10,
                    allowed_sources=None,
                    require_source_filter=False,
                    owner=None,
                )
                # similarity_search returns (Document, score) pairs, not dicts.
                retrieved_docs = [document.metadata.get("source", "") for document, _score in results]
            elif self.system_name == "hybrid":
                results, _ = hybrid_search_with_diagnostics(
                    query=query,
                    allowed_sources=None,
                    # Offline harness measuring retrieval quality over a fixed
                    # corpus: there is no request and no user to scope to. Written
                    # out rather than defaulted, and allowlisted in
                    # tests/security/test_no_unrestricted_retrieval.py.
                    owner=None,
                )
                retrieved_docs = [doc.get("source", "") for doc in results]
            else:
                raise ValueError(f"Unknown system: {self.system_name}")

            return _result(query_id, query, retrieved_docs, start_time)
        except Exception:
            logger.exception(f"Retrieval failed for query '{query}'")
            return _result(query_id, query, [], start_time)

    def batch_retrieve(self, queries: list[tuple[str, str]]) -> list[RetrievalResult]:
        """Retrieve documents for multiple evaluation queries."""
        return [self.retrieve(query_text, query_id) for query_text, query_id in queries]


def create_api_retriever(system_name: str) -> SimpleRetriever:
    """Build a named evaluation baseline or reject an unsupported system."""
    if system_name not in SUPPORTED_SYSTEMS:
        raise ValueError(f"Unknown system: {system_name}. Available systems: {', '.join(SUPPORTED_SYSTEMS)}")
    return SimpleRetriever(system_name)
