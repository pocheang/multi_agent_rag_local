"""Vector-only baseline retrieval system."""

import time

from langchain_chroma import Chroma

from app.evaluation.models import RetrievalResult


class VectorBaseline:
    """Simple vector similarity baseline using Chroma."""

    def __init__(self, vectorstore: Chroma, k: int = 5, score_threshold: float | None = None):
        """Initialize vector baseline.

        Args:
            vectorstore: Chroma vectorstore instance
            k: Number of documents to retrieve
            score_threshold: Optional minimum similarity score
        """
        self.vectorstore = vectorstore
        self.k = k
        self.score_threshold = score_threshold

    def retrieve(self, query: str, query_id: str = "") -> RetrievalResult:
        """Retrieve documents using vector similarity.

        Args:
            query: Query text
            query_id: Optional query identifier

        Returns:
            RetrievalResult with retrieved documents and metadata
        """
        start_time = time.perf_counter()

        # Perform similarity search with scores
        if self.score_threshold is not None:
            results = self.vectorstore.similarity_search_with_relevance_scores(
                query, k=self.k, score_threshold=self.score_threshold
            )
        else:
            results = self.vectorstore.similarity_search_with_relevance_scores(query, k=self.k)

        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000

        # Extract document IDs and scores
        doc_ids = []
        scores = []
        for doc, score in results:
            # Use document metadata ID if available, otherwise use page_content hash
            doc_id = doc.metadata.get("id", str(hash(doc.page_content)))
            doc_ids.append(doc_id)
            scores.append(score)

        return RetrievalResult(
            query_id=query_id or query,
            query_text=query,
            retrieved_docs=doc_ids,
            scores=scores,
            latency_ms=latency_ms,
            metadata={
                "method": "vector_only",
                "k": self.k,
                "score_threshold": self.score_threshold,
            },
        )

    def batch_retrieve(self, queries: list[tuple[str, str]]) -> list[RetrievalResult]:
        """Retrieve documents for multiple queries.

        Args:
            queries: List of (query_text, query_id) tuples

        Returns:
            List of RetrievalResult objects
        """
        return [self.retrieve(query, query_id) for query, query_id in queries]


def create_vector_baseline(vectorstore: Chroma, k: int = 5, score_threshold: float | None = None) -> VectorBaseline:
    """Factory function to create a vector baseline.

    Args:
        vectorstore: Chroma vectorstore instance
        k: Number of documents to retrieve
        score_threshold: Optional minimum similarity score

    Returns:
        Configured VectorBaseline instance
    """
    return VectorBaseline(vectorstore=vectorstore, k=k, score_threshold=score_threshold)
