"""Compatibility re-export for app.agents.rag.retrieval_quality; implementation lives in the canonical package."""

from app.agents.rag.retrieval_quality import (
    evaluate_retrieval_quality,
)

__all__ = [
    "evaluate_retrieval_quality",
]
