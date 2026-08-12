"""Public pipeline boundary."""

from typing import TYPE_CHECKING, Any

from app.pipeline.contracts import (
    ConversationMessage,
    PipelineRequest,
    PipelineResult,
    SourceScope,
)
from app.pipeline.profiles import PipelineProfile

if TYPE_CHECKING:
    from app.pipeline.rag_pipeline import RAGPipeline

__all__ = [
    "ConversationMessage",
    "PipelineRequest",
    "PipelineResult",
    "SourceScope",
    "PipelineProfile",
    "RAGPipeline",
]


def __getattr__(name: str) -> Any:
    """Resolve heavyweight pipeline implementations only when requested."""
    if name == "RAGPipeline":
        from app.pipeline.rag_pipeline import RAGPipeline

        return RAGPipeline
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
