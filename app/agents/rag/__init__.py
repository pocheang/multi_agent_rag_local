"""Typed RAG service adapter with a lazy public service export."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.rag.service import RAGAgentService

__all__ = ["RAGAgentService"]


def __getattr__(name: str):
    """Load the RAG service only when it is requested."""
    if name == "RAGAgentService":
        from app.agents.rag.service import RAGAgentService

        return RAGAgentService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
