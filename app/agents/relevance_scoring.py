"""Compatibility re-export for app.agents.rag.relevance; implementation lives in the canonical package."""

from app.agents.rag.relevance import (
    BatchRelevanceResult,
    RelevanceScore,
    batch_score_relevance,
    score_relevance,
)

__all__ = [
    "RelevanceScore",
    "BatchRelevanceResult",
    "score_relevance",
    "batch_score_relevance",
]
