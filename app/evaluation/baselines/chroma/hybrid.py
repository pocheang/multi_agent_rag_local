"""Hybrid baseline combining vector similarity and BM25."""

import time

from langchain_chroma import Chroma
from rank_bm25 import BM25Okapi

from app.evaluation.models import RetrievalResult


class HybridBaseline:
    """Hybrid retrieval combining vector similarity and BM25."""

    def __init__(
        self,
        vectorstore: Chroma,
        bm25_index: BM25Okapi,
        doc_id_map: dict[int, str],
        k: int = 5,
        alpha: float = 0.5,
        score_threshold: float | None = None,
    ):
        """Initialize hybrid baseline.

        Args:
            vectorstore: Chroma vectorstore instance
            bm25_index: BM25 index for keyword search
            doc_id_map: Mapping from BM25 index position to document ID
            k: Number of documents to retrieve
            alpha: Weight for vector scores (1-alpha for BM25). 0.5 = equal weight
            score_threshold: Optional minimum combined score
        """
        self.vectorstore = vectorstore
        self.bm25_index = bm25_index
        self.doc_id_map = doc_id_map
        self.k = k
        self.alpha = alpha
        self.score_threshold = score_threshold

    def retrieve(self, query: str, query_id: str = "") -> RetrievalResult:
        """Retrieve documents using hybrid search.

        Args:
            query: Query text
            query_id: Optional query identifier

        Returns:
            RetrievalResult with retrieved documents and metadata
        """
        start_time = time.perf_counter()

        # Get vector search results
        vector_results = self.vectorstore.similarity_search_with_relevance_scores(
            query,
            k=self.k * 2,  # Retrieve more for fusion
        )

        # Get BM25 results
        tokenized_query = query.lower().split()
        bm25_scores = self.bm25_index.get_scores(tokenized_query)

        # Normalize scores to [0, 1]
        vector_scores_dict = {}
        for doc, score in vector_results:
            doc_id = doc.metadata.get("id", str(hash(doc.page_content)))
            vector_scores_dict[doc_id] = score

        # Normalize BM25 scores
        max_bm25 = max(bm25_scores) if max(bm25_scores) > 0 else 1.0
        bm25_scores_dict = {}
        for idx, score in enumerate(bm25_scores):
            if idx in self.doc_id_map:
                doc_id = self.doc_id_map[idx]
                bm25_scores_dict[doc_id] = score / max_bm25

        # Combine scores using weighted average
        combined_scores = {}
        all_doc_ids = set(vector_scores_dict.keys()) | set(bm25_scores_dict.keys())

        for doc_id in all_doc_ids:
            vector_score = vector_scores_dict.get(doc_id, 0.0)
            bm25_score = bm25_scores_dict.get(doc_id, 0.0)
            combined_score = self.alpha * vector_score + (1 - self.alpha) * bm25_score

            if self.score_threshold is None or combined_score >= self.score_threshold:
                combined_scores[doc_id] = combined_score

        # Sort by combined score and take top-k
        sorted_docs = sorted(combined_scores.items(), key=lambda x: x[1], reverse=True)[: self.k]

        doc_ids = [doc_id for doc_id, _ in sorted_docs]
        scores = [score for _, score in sorted_docs]

        end_time = time.perf_counter()
        latency_ms = (end_time - start_time) * 1000

        return RetrievalResult(
            query_id=query_id or query,
            query_text=query,
            retrieved_docs=doc_ids,
            scores=scores,
            latency_ms=latency_ms,
            metadata={
                "method": "hybrid",
                "k": self.k,
                "alpha": self.alpha,
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


def create_hybrid_baseline(
    vectorstore: Chroma,
    bm25_index: BM25Okapi,
    doc_id_map: dict[int, str],
    k: int = 5,
    alpha: float = 0.5,
    score_threshold: float | None = None,
) -> HybridBaseline:
    """Factory function to create a hybrid baseline.

    Args:
        vectorstore: Chroma vectorstore instance
        bm25_index: BM25 index for keyword search
        doc_id_map: Mapping from BM25 index position to document ID
        k: Number of documents to retrieve
        alpha: Weight for vector scores (1-alpha for BM25)
        score_threshold: Optional minimum combined score

    Returns:
        Configured HybridBaseline instance
    """
    return HybridBaseline(
        vectorstore=vectorstore,
        bm25_index=bm25_index,
        doc_id_map=doc_id_map,
        k=k,
        alpha=alpha,
        score_threshold=score_threshold,
    )
