"""Enhanced vector retrieval with optional Self-RAG evaluation."""

import logging
import os
from typing import Any

from app.agents.rag.vector import run_vector_rag
from app.services.self_rag_evaluator import SelfRAGEvaluator

logger = logging.getLogger(__name__)

__all__ = ["EnhancedVectorRAGAgent", "run_vector_rag_with_evaluation"]


class EnhancedVectorRAGAgent:
    """Vector RAG agent with Self-RAG evaluation capability."""

    def __init__(self, llm_client, enable_self_rag: bool = None):
        """
        Initialize enhanced vector RAG agent.

        Args:
            llm_client: LLM client for Self-RAG evaluation
            enable_self_rag: Whether to enable Self-RAG evaluation
                            (defaults to ENABLE_SELF_RAG env var)
        """
        if enable_self_rag is None:
            enable_self_rag = os.getenv("ENABLE_SELF_RAG", "false").lower() == "true"

        self.enable_self_rag = enable_self_rag
        self.self_rag_evaluator = None

        if self.enable_self_rag:
            self.self_rag_evaluator = SelfRAGEvaluator(llm_client)
            logger.info("Self-RAG evaluation enabled")

    async def retrieve_with_evaluation(
        self,
        question: str,
        allowed_sources: list[str] | None = None,
        agent_class: str | None = None,
    ) -> dict[str, Any]:
        """
        Retrieve documents with optional Self-RAG evaluation.

        Args:
            question: User query
            allowed_sources: Optional list of allowed sources

        Returns:
            Dictionary with retrieval results and optional evaluation
        """
        rag_result = run_vector_rag(
            question,
            allowed_sources,
            agent_class=agent_class,
        )

        result = {
            "question": question,
            "context": rag_result["context"],
            "citations": rag_result["citations"],
            "retrieved_count": rag_result["retrieved_count"],
            "effective_hit_count": rag_result["effective_hit_count"],
            "retrieval_diagnostics": rag_result["retrieval_diagnostics"],
            "relevance_scores": None,
            "filtered_citations": None,
        }

        if self.enable_self_rag and self.self_rag_evaluator:
            try:
                documents = self._citations_to_documents(rag_result["citations"])
                relevance_scores = await self.self_rag_evaluator.evaluate_retrieval_relevance(question, documents)
                result["relevance_scores"] = [score.model_dump() for score in relevance_scores]

                filtered_docs = self.self_rag_evaluator.filter_relevant_documents(documents, relevance_scores)
                filtered_citations = self._documents_to_citations(filtered_docs)
                result["filtered_citations"] = filtered_citations
                result["filtered_count"] = len(filtered_citations)

                if filtered_citations:
                    context_blocks = []
                    for citation in filtered_citations:
                        src = citation["source"]
                        chunk = citation["content"]
                        retrieval_sources = citation["metadata"].get("retrieval_sources", [])
                        context_blocks.append(f"[SOURCE: {src}]\n[RETRIEVAL: {','.join(retrieval_sources)}]\n{chunk}")
                    result["filtered_context"] = "\n\n".join(context_blocks)

                logger.info(
                    f"Self-RAG filtered {result['retrieved_count']} documents to "
                    f"{result['filtered_count']} relevant documents"
                )

            except Exception as e:
                logger.error(f"Error during Self-RAG evaluation: {e}", exc_info=True)

        return result

    async def evaluate_answer_quality(
        self, question: str, answer: str, citations: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """Evaluate generated-answer quality when Self-RAG is enabled."""
        if not self.enable_self_rag or not self.self_rag_evaluator:
            return None

        try:
            documents = self._citations_to_documents(citations)
            quality = await self.self_rag_evaluator.evaluate_answer_quality(question, answer, documents)
            return quality.model_dump()
        except Exception as e:
            logger.error(f"Error evaluating answer quality: {e}", exc_info=True)
            return None

    def _citations_to_documents(self, citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert citations to document format for evaluation."""
        documents = []
        for i, citation in enumerate(citations):
            documents.append(
                {
                    "id": citation.get("metadata", {}).get("id", f"doc_{i}"),
                    "content": citation.get("content", ""),
                    "metadata": citation.get("metadata", {}),
                }
            )
        return documents

    def _documents_to_citations(self, documents: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert documents back to citations format."""
        citations = []
        for doc in documents:
            citations.append(
                {
                    "source": doc.get("metadata", {}).get("source", "unknown"),
                    "content": doc.get("content", ""),
                    "metadata": doc.get("metadata", {}),
                }
            )
        return citations


def run_vector_rag_with_evaluation(
    question: str,
    allowed_sources: list[str] | None = None,
    agent_class: str | None = None,
) -> dict[str, Any]:
    """Synchronous compatibility wrapper for vector retrieval."""
    return run_vector_rag(
        question,
        allowed_sources,
        agent_class=agent_class,
    )
