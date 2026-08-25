"""Visual embedding provider boundary."""

from app.ingestion.embedding.visual import (
    CallableVisualEmbeddingProvider,
    DescriptionEmbeddingFallback,
    VisualEmbeddingProvider,
    VisualEmbeddingResult,
    build_visual_embedding_provider,
)

__all__ = [
    "CallableVisualEmbeddingProvider",
    "DescriptionEmbeddingFallback",
    "VisualEmbeddingProvider",
    "VisualEmbeddingResult",
    "build_visual_embedding_provider",
]
