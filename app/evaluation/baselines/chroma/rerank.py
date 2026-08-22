"""Rerank baseline using cross-encoder for reranking."""

import time
from collections.abc import Callable

from langchain_chroma import Chroma

from app.evaluation.models import RetrievalResult


class RerankBaseline:
    """Retrieval with reranking using a cross-encoder model."""

    def __init__(
        self,
        vectorstore: Chroma,
        rerank_fn: Callable[[str, list[str]], list[float]],
        k: int = 5,
        initial_k: int = 20,
        score_threshold: float | None = None,
    ):
        """Initialize rerank baseline.

        Args:
            vectorstore: Chroma vectorstore instance
            rerank_fn: Function that takes (query, docs) and returns rerank scores
            k: Number of documents to return after reranking
            initial_k: Number of documents to retrieve before reranking
            score_threshold: Optional minimum rerank score
        """
        self.vectorstore = vectorstore
        self.rerank_fn = rerank_fn
        self.k = k
        self.initial_k = initial_k
        self.score_threshold = score_threshold

    def retrieve(self, query: str, query_id: str = "") -> RetrievalResult:
        """Retrieve and rerank documents.

        Args:
            query: Query text
            query_id: Optional query identifier

        Returns:
            RetrievalResult with reranked documents and metadata
        """
        start_time = time.perf_counter()

        # Initial retrieval with larger k
        initial_results = self.vectorstore.similarity_search_with_relevance_scores(query, k=self.initial_k)

        if not initial_results:
            end_time = time.perf_counter()
            return RetrievalResult(
                query_id=query_id or query,
                query_text=query,
                retrieved_docs=[],
                scores=[],
                latency_ms=(end_time - start_time) * 1000,
                metadata={
                    "method": "rerank",
                    "k": self.k,
                    "initial_k": self.initial_k,
                },
            )

        # Extract documents and IDs
        docs = [doc for doc, _ in initial_results]
        doc_ids = [doc.metadata.get("id", str(hash(doc.page_content))) for doc in docs]
        doc_texts = [doc.page_content for doc in docs]

        # Rerank using cross-encoder
        rerank_scores = self.rerank_fn(query, doc_texts)

        # Combine doc IDs with rerank scores
        doc_score_pairs = list(zip(doc_ids, rerank_scores, strict=False))

        # Filter by threshold if specified
        if self.score_threshold is not None:
            doc_score_pairs = [(doc_id, score) for doc_id, score in doc_score_pairs if score >= self.score_threshold]

        # Sort by rerank score and take top-k
        doc_score_pairs.sort(key=lambda x: x[1], reverse=True)
        doc_score_pairs = doc_score_pairs[: self.k]

        final_doc_ids = [doc_id for doc_id, _ in doc_score_pairs]
        final_scores = [score for _, score in doc_score_pairs]

        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000

        return RetrievalResult(
            query_id=query_id or query,
            query_text=query,
            retrieved_docs=final_doc_ids,
            scores=final_scores,
            latency_ms=latency_ms,
            metadata={
                "method": "rerank",
                "k": self.k,
                "initial_k": self.initial_k,
                "score_threshold": self.score_threshold,
            },
        )

    def batch_retrieve(self, queries: list[tuple[str, str]]) -> list[RetrievalResult]:
        """Retrieve and rerank documents for multiple queries.

        Args:
            queries: List of (query_text, query_id) tuples

        Returns:
            List of RetrievalResult objects
        """
        return [self.retrieve(query, query_id) for query, query_id in queries]


def create_rerank_baseline(
    vectorstore: Chroma,
    rerank_fn: Callable[[str, list[str]], list[float]],
    k: int = 5,
    initial_k: int = 20,
    score_threshold: float | None = None,
) -> RerankBaseline:
    """Factory function to create a rerank baseline.

    Args:
        vectorstore: Chroma vectorstore instance
        rerank_fn: Function that takes (query, docs) and returns rerank scores
        k: Number of documents to return after reranking
        initial_k: Number of documents to retrieve before reranking
        score_threshold: Optional minimum rerank score

    Returns:
        Configured RerankBaseline instance
    """
    return RerankBaseline(
        vectorstore=vectorstore, rerank_fn=rerank_fn, k=k, initial_k=initial_k, score_threshold=score_threshold
    )
