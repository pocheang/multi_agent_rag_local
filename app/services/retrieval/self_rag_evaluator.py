"""
Self-RAG evaluator service for evaluating retrieval relevance and answer quality.
"""

import logging
import os
import re
from typing import Any

from app.domain.advanced_rag import AnswerQuality, RelevanceScore

logger = logging.getLogger(__name__)


class SelfRAGEvaluator:
    """Service for evaluating retrieval relevance and answer quality."""

    def __init__(self, llm_client):
        """
        Initialize Self-RAG evaluator.

        Args:
            llm_client: LLM client for evaluation
        """
        self.llm = llm_client
        self.relevance_prompt = self._load_relevance_prompt()
        self.quality_prompt = self._load_quality_prompt()
        self.relevance_threshold = float(os.getenv("SELF_RAG_RELEVANCE_THRESHOLD", "0.6"))
        self.quality_threshold = float(os.getenv("SELF_RAG_QUALITY_THRESHOLD", "0.7"))

    def _load_relevance_prompt(self) -> str:
        """Load relevance evaluation prompt template."""
        return """Evaluate the relevance of the following document to the query.

Query: {query}
Document: {document}

Rate the relevance on a scale of 0-10, where:
- 0-3: Not relevant (document doesn't address the query)
- 4-6: Partially relevant (document has some related information)
- 7-10: Highly relevant (document directly answers the query)

Output format:
Score: [0-10]
Reasoning: [brief explanation]"""

    def _load_quality_prompt(self) -> str:
        """Load quality evaluation prompt template."""
        return """Evaluate the quality of the following answer to the query.

Query: {query}
Answer: {answer}
Source Documents: {documents}

Rate the answer on these aspects (0-1 scale):
- Completeness: Does it address all aspects of the query?
- Accuracy: Is it factually correct based on the documents?
- Relevance: Is it directly relevant to the query?

Output format:
Completeness: [0-1]
Accuracy: [0-1]
Relevance: [0-1]
Overall Score: [0-1]
Feedback: [brief explanation]"""

    async def evaluate_retrieval_relevance(self, query: str, documents: list[dict[str, Any]]) -> list[RelevanceScore]:
        """
        Evaluate relevance of each retrieved document to the query.

        Args:
            query: User query
            documents: List of retrieved documents

        Returns:
            List of relevance scores for each document
        """
        relevance_scores = []

        for doc in documents:
            try:
                # Extract document content (handle different document formats)
                content = doc.get("content", doc.get("page_content", ""))
                doc_id = doc.get("id", doc.get("metadata", {}).get("id", str(hash(content[:100]))))

                # Use first 500 characters for evaluation
                doc_preview = content[:500]

                prompt = self.relevance_prompt.format(query=query, document=doc_preview)

                # Use ainvoke for compatibility with LangChain 0.3+ API
                response = await self.llm.ainvoke(prompt)
                response_text = response.content if hasattr(response, "content") else str(response)

                score = self._parse_relevance_score(response_text)
                relevance_scores.append(
                    RelevanceScore(document_id=str(doc_id), score=score, reasoning=response_text.strip())
                )

            except Exception as e:
                logger.error(f"Error evaluating document relevance: {e}")
                # Default to medium relevance on error
                relevance_scores.append(
                    RelevanceScore(
                        document_id=str(doc.get("id", "unknown")),
                        score=0.5,
                        reasoning=f"Error during evaluation: {str(e)}",
                    )
                )

        return relevance_scores

    def filter_relevant_documents(
        self, documents: list[dict[str, Any]], relevance_scores: list[RelevanceScore]
    ) -> list[dict[str, Any]]:
        """
        Filter documents based on relevance threshold.

        Args:
            documents: List of documents
            relevance_scores: Relevance scores for each document

        Returns:
            Filtered list of relevant documents
        """
        relevant_docs = []
        for doc, score in zip(documents, relevance_scores, strict=False):
            if score.score >= self.relevance_threshold:
                relevant_docs.append(doc)
            else:
                logger.debug(f"Filtered out document (score={score.score:.2f}): {score.document_id}")

        logger.info(f"Filtered {len(documents)} documents to {len(relevant_docs)} relevant documents")
        return relevant_docs

    async def evaluate_answer_quality(self, query: str, answer: str, documents: list[dict[str, Any]]) -> AnswerQuality:
        """
        Evaluate quality of generated answer.

        Args:
            query: User query
            answer: Generated answer
            documents: Source documents used for generation

        Returns:
            AnswerQuality with scores and feedback
        """
        try:
            # Format documents for prompt
            docs_text = self._format_documents(documents)

            prompt = self.quality_prompt.format(query=query, answer=answer, documents=docs_text)

            # Use ainvoke for compatibility with LangChain 0.3+ API
            response = await self.llm.ainvoke(prompt)
            response_text = response.content if hasattr(response, "content") else str(response)

            quality = self._parse_quality_evaluation(response_text)

            return AnswerQuality(
                score=quality["score"],
                completeness=quality["completeness"],
                accuracy=quality["accuracy"],
                relevance=quality["relevance"],
                feedback=response_text.strip(),
                needs_refinement=quality["score"] < self.quality_threshold,
            )

        except Exception as e:
            logger.error(f"Error evaluating answer quality: {e}")
            # Return default quality on error
            return AnswerQuality(
                score=0.5,
                completeness=0.5,
                accuracy=0.5,
                relevance=0.5,
                feedback=f"Error during evaluation: {str(e)}",
                needs_refinement=True,
            )

    def _parse_relevance_score(self, response: str) -> float:
        """
        Parse relevance score from LLM response.

        Args:
            response: LLM response text

        Returns:
            Relevance score (0-1)
        """
        # Look for score in format "Score: 8/10" or "8/10"
        match = re.search(r"(\d+\.?\d*)\s*/\s*10", response)
        if match:
            return float(match.group(1)) / 10

        # Look for score in format "Score: 0.8"
        match = re.search(r"Score:\s*(\d+\.?\d*)", response, re.IGNORECASE)
        if match:
            score = float(match.group(1))
            # If score is > 1, assume it's out of 10
            if score > 1:
                score = score / 10
            return min(1.0, max(0.0, score))

        # Default to medium relevance if can't parse
        logger.warning(f"Could not parse relevance score from: {response}")
        return 0.5

    def _parse_quality_evaluation(self, response: str) -> dict[str, float]:
        """
        Parse quality evaluation from LLM response.

        Args:
            response: LLM response text

        Returns:
            Dictionary with quality scores
        """
        quality = {"score": 0.5, "completeness": 0.5, "accuracy": 0.5, "relevance": 0.5}

        # Extract scores for each aspect
        for aspect in ["completeness", "accuracy", "relevance"]:
            pattern = rf"{aspect}:\s*(\d+\.?\d*)"
            match = re.search(pattern, response, re.IGNORECASE)
            if match:
                score = float(match.group(1))
                # If score is > 1, assume it's out of 10
                if score > 1:
                    score = score / 10
                quality[aspect] = min(1.0, max(0.0, score))

        # Extract overall score
        pattern = r"Overall\s+Score:\s*(\d+\.?\d*)"
        match = re.search(pattern, response, re.IGNORECASE)
        if match:
            score = float(match.group(1))
            if score > 1:
                score = score / 10
            quality["score"] = min(1.0, max(0.0, score))
        else:
            # Calculate overall score as average if not provided
            quality["score"] = (quality["completeness"] + quality["accuracy"] + quality["relevance"]) / 3

        return quality

    def _format_documents(self, documents: list[dict[str, Any]]) -> str:
        """
        Format documents for prompt.

        Args:
            documents: List of documents

        Returns:
            Formatted document text
        """
        formatted = []
        for i, doc in enumerate(documents[:3], 1):  # Limit to 3 documents
            content = doc.get("content", doc.get("page_content", ""))
            preview = content[:200]  # First 200 chars
            formatted.append(f"Document {i}: {preview}...")

        return "\n".join(formatted)
