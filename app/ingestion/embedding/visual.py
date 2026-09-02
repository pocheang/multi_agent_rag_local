"""Optional visual embeddings with an explicit description fallback."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from app.core.config import Settings, get_settings


@dataclass(frozen=True)
class VisualEmbeddingResult:
    vector: tuple[float, ...]
    model: str
    backend: str
    fallback_reason: str | None = None


class VisualEmbeddingProvider(Protocol):
    async def embed_image(self, content: bytes, *, description: str = "") -> VisualEmbeddingResult: ...

    async def embed_page(self, content: bytes, *, description: str = "") -> VisualEmbeddingResult: ...

    async def embed_query(self, query: str) -> VisualEmbeddingResult: ...


VisualEmbedder = Callable[[bytes], Awaitable[tuple[float, ...]]]
VisualQueryEmbedder = Callable[[str], Awaitable[tuple[float, ...]]]


class CallableVisualEmbeddingProvider:
    """ColPali-compatible adapter supplied by an installed provider factory."""

    def __init__(
        self,
        embed: VisualEmbedder,
        embed_query: VisualQueryEmbedder,
        *,
        model: str,
        backend: str = "colpali",
    ) -> None:
        self._embed = embed
        self._embed_query = embed_query
        self._model = model
        self._backend = backend

    async def embed_image(self, content: bytes, *, description: str = "") -> VisualEmbeddingResult:
        del description
        return VisualEmbeddingResult(vector=await self._embed(content), model=self._model, backend=self._backend)

    async def embed_page(self, content: bytes, *, description: str = "") -> VisualEmbeddingResult:
        return await self.embed_image(content, description=description)

    async def embed_query(self, query: str) -> VisualEmbeddingResult:
        return VisualEmbeddingResult(
            vector=await self._embed_query(query),
            model=self._model,
            backend=self._backend,
        )


class DescriptionEmbeddingFallback:
    """Embed governed OCR/description text when a visual model is unavailable."""

    def __init__(self, *, reason: str = "visual_provider_disabled") -> None:
        self._reason = reason

    async def embed_image(self, content: bytes, *, description: str = "") -> VisualEmbeddingResult:
        del content
        from app.services.models.runtime import get_embedding_model

        text = description.strip() or "Image with no generated description"
        model = get_embedding_model()
        vector = await asyncio.to_thread(model.embed_query, text)
        return VisualEmbeddingResult(
            vector=tuple(float(value) for value in vector),
            model=type(model).__name__,
            backend="description_fallback",
            fallback_reason=self._reason,
        )

    async def embed_page(self, content: bytes, *, description: str = "") -> VisualEmbeddingResult:
        return await self.embed_image(content, description=description)

    async def embed_query(self, query: str) -> VisualEmbeddingResult:
        from app.services.models.runtime import get_embedding_model

        model = get_embedding_model()
        vector = await asyncio.to_thread(model.embed_query, query.strip())
        return VisualEmbeddingResult(
            vector=tuple(float(value) for value in vector),
            model=type(model).__name__,
            backend="description_fallback",
            fallback_reason=self._reason,
        )


def build_visual_embedding_provider(
    settings: Settings | None = None,
    *,
    colpali_factory: Callable[[], VisualEmbeddingProvider] | None = None,
) -> VisualEmbeddingProvider:
    active = settings or get_settings()
    if not active.visual_embedding_enabled:
        return DescriptionEmbeddingFallback(reason="visual_embedding_disabled")
    if active.visual_embedding_backend == "colpali" and colpali_factory is not None:
        try:
            return colpali_factory()
        except Exception as exc:
            return DescriptionEmbeddingFallback(reason=f"colpali_factory_failed:{type(exc).__name__}")
    reason = (
        "colpali_provider_not_configured" if active.visual_embedding_backend == "colpali" else "visual_backend_unknown"
    )
    return DescriptionEmbeddingFallback(reason=reason)


__all__ = [
    "CallableVisualEmbeddingProvider",
    "DescriptionEmbeddingFallback",
    "VisualEmbeddingProvider",
    "VisualEmbeddingResult",
    "VisualQueryEmbedder",
    "build_visual_embedding_provider",
]
