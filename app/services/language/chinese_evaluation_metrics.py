"""Chinese-specific evaluation metrics for RAG systems."""

import logging
from typing import Any

from app.services.language.chinese_tokenizer import get_tokenizer

logger = logging.getLogger(__name__)


class ChineseEvaluationMetrics:
    """Evaluation metrics tailored for Chinese text retrieval."""

    def __init__(self):
        """Initialize the metrics calculator."""
        self.tokenizer = get_tokenizer()

    def token_overlap_score(self, query_tokens: list[str], document_tokens: list[str]) -> float:
        """Calculate token overlap between query and document.

        Args:
            query_tokens: Tokenized query
            document_tokens: Tokenized document

        Returns:
            Overlap score (0-1)
        """
        if not query_tokens or not document_tokens:
            return 0.0

        query_set = set(query_tokens)
        doc_set = set(document_tokens)

        intersection = query_set & doc_set
        union = query_set | doc_set

        if not union:
            return 0.0

        return len(intersection) / len(union)

    def keyword_coverage(self, query: str, document: str, topK: int = 5) -> float:
        """Calculate how many query keywords appear in the document.

        Args:
            query: Query text
            document: Document text
            topK: Number of top keywords to extract

        Returns:
            Coverage score (0-1)
        """
        # Extract keywords from query
        query_keywords = self.tokenizer.extract_keywords(query, topK=topK)

        if not query_keywords:
            return 0.0

        # Tokenize document
        doc_tokens = set(self.tokenizer.tokenize(document))

        # Count how many keywords appear in document
        covered = sum(1 for kw in query_keywords if kw in doc_tokens)

        return covered / len(query_keywords)

    def semantic_density(self, text: str) -> float:
        """Calculate semantic density of text based on keyword concentration.

        Higher density indicates more information-rich content.

        Args:
            text: Input text

        Returns:
            Density score (0-1)
        """
        tokens = self.tokenizer.tokenize(text)
        if not tokens:
            return 0.0

        # Extract keywords with weights
        keywords = self.tokenizer.extract_keywords(text, topK=min(10, len(tokens)), withWeight=True)

        if not keywords:
            return 0.0

        # Average keyword weight as density measure
        avg_weight = sum(w for _, w in keywords) / len(keywords)

        # Normalize to 0-1 range (TF-IDF weights are typically 0-1)
        return min(1.0, avg_weight)

    def calculate_chinese_metrics(
        self, query: str, retrieved_documents: list[str], relevant_indices: list[int] | None = None
    ) -> dict[str, Any]:
        """Calculate comprehensive Chinese-specific metrics.

        Args:
            query: Query text
            retrieved_documents: List of retrieved document texts
            relevant_indices: Indices of relevant documents (for precision/recall)

        Returns:
            Dictionary of metrics
        """
        if not retrieved_documents:
            return {
                "token_overlap_scores": [],
                "keyword_coverage_scores": [],
                "semantic_density_scores": [],
                "avg_token_overlap": 0.0,
                "avg_keyword_coverage": 0.0,
                "avg_semantic_density": 0.0,
            }

        # Tokenize query once
        query_tokens = self.tokenizer.tokenize_for_search(query)

        # Calculate metrics for each document
        token_overlap_scores = []
        keyword_coverage_scores = []
        semantic_density_scores = []

        for doc in retrieved_documents:
            # Token overlap
            doc_tokens = self.tokenizer.tokenize(doc)
            overlap = self.token_overlap_score(query_tokens, doc_tokens)
            token_overlap_scores.append(overlap)

            # Keyword coverage
            coverage = self.keyword_coverage(query, doc)
            keyword_coverage_scores.append(coverage)

            # Semantic density
            density = self.semantic_density(doc)
            semantic_density_scores.append(density)

        metrics = {
            "token_overlap_scores": token_overlap_scores,
            "keyword_coverage_scores": keyword_coverage_scores,
            "semantic_density_scores": semantic_density_scores,
            "avg_token_overlap": sum(token_overlap_scores) / len(token_overlap_scores),
            "avg_keyword_coverage": sum(keyword_coverage_scores) / len(keyword_coverage_scores),
            "avg_semantic_density": sum(semantic_density_scores) / len(semantic_density_scores),
        }

        # If relevance labels provided, calculate precision/recall
        if relevant_indices is not None:
            relevant_set = set(relevant_indices)
            retrieved_set = set(range(len(retrieved_documents)))

            true_positives = len(relevant_set & retrieved_set)
            precision = true_positives / len(retrieved_set) if retrieved_set else 0.0
            recall = true_positives / len(relevant_set) if relevant_set else 0.0
            f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0.0

            metrics.update({"precision": precision, "recall": recall, "f1_score": f1})

        return metrics

    def compare_systems(
        self, query: str, system_results: dict[str, list[str]], relevant_indices: list[int] | None = None
    ) -> dict[str, dict[str, Any]]:
        """Compare multiple retrieval systems on Chinese metrics.

        Args:
            query: Query text
            system_results: Dict mapping system name to retrieved documents
            relevant_indices: Indices of relevant documents

        Returns:
            Dict mapping system name to metrics
        """
        comparison = {}

        for system_name, documents in system_results.items():
            metrics = self.calculate_chinese_metrics(query, documents, relevant_indices)
            comparison[system_name] = metrics

        return comparison

    def rank_documents_by_chinese_score(
        self, query: str, documents: list[str], weights: dict[str, float] | None = None
    ) -> list[tuple[int, float]]:
        """Rank documents using Chinese-specific scoring.

        Args:
            query: Query text
            documents: List of documents
            weights: Optional weights for different metrics
                    {"token_overlap": 0.4, "keyword_coverage": 0.4, "semantic_density": 0.2}

        Returns:
            List of (document_index, score) tuples, sorted by score descending
        """
        if weights is None:
            weights = {"token_overlap": 0.4, "keyword_coverage": 0.4, "semantic_density": 0.2}

        # Calculate metrics
        metrics = self.calculate_chinese_metrics(query, documents)

        # Compute weighted scores
        scores = []
        for i in range(len(documents)):
            score = (
                weights["token_overlap"] * metrics["token_overlap_scores"][i]
                + weights["keyword_coverage"] * metrics["keyword_coverage_scores"][i]
                + weights["semantic_density"] * metrics["semantic_density_scores"][i]
            )
            scores.append((i, score))

        # Sort by score descending
        scores.sort(key=lambda x: x[1], reverse=True)

        return scores


# Global metrics instance
_metrics: ChineseEvaluationMetrics | None = None


def get_metrics() -> ChineseEvaluationMetrics:
    """Get or create the global metrics instance."""
    global _metrics
    if _metrics is None:
        _metrics = ChineseEvaluationMetrics()
    return _metrics
