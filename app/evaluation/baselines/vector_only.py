"""Vector-only baseline retriever."""

import time

from app.evaluation.models import RetrievalResult
from app.retrievers.stores.vector import similarity_search


class VectorOnlyRetriever:
    """Pure vector similarity search baseline."""

    def __init__(self):
        """Initialize vector-only retriever."""
        pass

    def retrieve(self, query: str, top_k: int = 5) -> RetrievalResult:
        """
        Retrieve documents using pure vector similarity search.

        Args:
            query: Query text
            top_k: Number of documents to retrieve

        Returns:
            RetrievalResult with retrieved documents and metadata
        """
        start_time = time.time()

        # Perform vector search
        results = similarity_search(query, k=top_k)

        latency_ms = (time.time() - start_time) * 1000

        # Format results
        retrieved_docs = []
        scores = []

        for doc, score in results:
            retrieved_docs.append(
                {
                    "id": doc.metadata.get("id", ""),
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "source": doc.metadata.get("source", ""),
                }
            )
            scores.append(float(score))

        return RetrievalResult(
            query_id="",  # Will be set by evaluation service
            query=query,
            retrieved_docs=retrieved_docs,
            scores=scores,
            latency_ms=latency_ms,
            metadata={"retriever": "vector_only", "top_k": top_k},
        )
