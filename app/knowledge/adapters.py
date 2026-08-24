"""Typed adapters over existing knowledge retrieval implementations."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence
from typing import Any, Protocol

from app.agents.rag.evidence_builder import (
    bundle_from_bm25_records,
    bundle_from_legacy_payload,
    bundle_from_vector_matches,
)
from app.domain.contracts import EvidenceItem
from app.domain.knowledge import AccessScope, KnowledgeSource, KnowledgeSourcePlan

AdapterCallable = Callable[[KnowledgeSourcePlan, AccessScope], Awaitable[tuple[EvidenceItem, ...]]]


class KnowledgeAdapter(Protocol):
    """Ordinary service adapter; retrievers are intentionally not Agents."""

    source: KnowledgeSource

    async def retrieve(
        self,
        plan: KnowledgeSourcePlan,
        scope: AccessScope,
    ) -> tuple[EvidenceItem, ...]: ...


class CallableKnowledgeAdapter:
    """Small dependency-injection adapter used by production and compatibility facades."""

    def __init__(self, source: KnowledgeSource, retrieve: AdapterCallable) -> None:
        self.source = source
        self._retrieve = retrieve

    async def retrieve(self, plan: KnowledgeSourcePlan, scope: AccessScope) -> tuple[EvidenceItem, ...]:
        return await self._retrieve(plan, scope)


class UnavailableKnowledgeSourceError(RuntimeError):
    """Raised when a selected optional source has no configured implementation."""


class UnavailableKnowledgeAdapter:
    """Explicit optional-source fallback, avoiding fabricated evidence."""

    def __init__(self, source: KnowledgeSource, reason: str) -> None:
        self.source = source
        self._reason = reason

    async def retrieve(self, plan: KnowledgeSourcePlan, scope: AccessScope) -> tuple[EvidenceItem, ...]:
        del plan, scope
        raise UnavailableKnowledgeSourceError(self._reason)


def build_default_adapters() -> dict[KnowledgeSource, KnowledgeAdapter]:
    """Build lazy wrappers over the repository's current retrievers."""

    return {
        "vector": CallableKnowledgeAdapter("vector", _retrieve_vector),
        "bm25": CallableKnowledgeAdapter("bm25", _retrieve_bm25),
        "graph": CallableKnowledgeAdapter("graph", _retrieve_graph),
        "multimodal": CallableKnowledgeAdapter("multimodal", _retrieve_multimodal),
        "web": CallableKnowledgeAdapter("web", _retrieve_web),
        "wiki": UnavailableKnowledgeAdapter("wiki", "LLM Wiki provider is not configured"),
        "memory": UnavailableKnowledgeAdapter("memory", "GBrain long-term memory provider is not configured"),
        "tool": UnavailableKnowledgeAdapter("tool", "tool retrieval is delegated to the governed Tool Agent"),
    }


async def _retrieve_vector(plan: KnowledgeSourcePlan, scope: AccessScope) -> tuple[EvidenceItem, ...]:
    from app.retrievers.stores.vector import similarity_search

    allowed = sorted(scope.allowed_sources)

    async def one(query: str) -> tuple[EvidenceItem, ...]:
        matches = await asyncio.to_thread(
            similarity_search,
            query,
            plan.top_k,
            allowed,
            False,
        )
        return bundle_from_vector_matches(matches).items

    return _flatten(await asyncio.gather(*(one(query) for query in plan.queries)))


async def _retrieve_bm25(plan: KnowledgeSourcePlan, scope: AccessScope) -> tuple[EvidenceItem, ...]:
    from app.retrievers.bm25_retriever import bm25_search

    allowed = sorted(scope.allowed_sources)

    async def one(query: str) -> tuple[EvidenceItem, ...]:
        records = await asyncio.to_thread(bm25_search, query, plan.top_k, allowed)
        return bundle_from_bm25_records(records).items

    return _flatten(await asyncio.gather(*(one(query) for query in plan.queries)))


async def _retrieve_graph(plan: KnowledgeSourcePlan, scope: AccessScope) -> tuple[EvidenceItem, ...]:
    from app.agents.rag.graph import run_graph_rag

    allowed = sorted(scope.allowed_sources)

    async def one(query: str) -> tuple[EvidenceItem, ...]:
        result = await asyncio.to_thread(run_graph_rag, query, allowed, None)
        bundle = bundle_from_legacy_payload(result, "graph", fallback_document_id=f"graph:{query}")
        return tuple(item.model_copy(update={"modality": "graph"}) for item in bundle.items)

    return _flatten(await asyncio.gather(*(one(query) for query in plan.queries)))


async def _retrieve_web(plan: KnowledgeSourcePlan, scope: AccessScope) -> tuple[EvidenceItem, ...]:
    from app.agents.rag.web import run_web_research

    async def one(query: str) -> tuple[EvidenceItem, ...]:
        result = await asyncio.to_thread(run_web_research, query, scope.user_id, None)
        bundle = bundle_from_legacy_payload(result, "web")
        return tuple(item.model_copy(update={"layer": "web"}) for item in bundle.items)

    return _flatten(await asyncio.gather(*(one(query) for query in plan.queries)))


async def _retrieve_multimodal(plan: KnowledgeSourcePlan, scope: AccessScope) -> tuple[EvidenceItem, ...]:
    from app.retrievers.multimodal_retriever import MultiModalRetriever

    retriever = MultiModalRetriever()

    async def one(query: str) -> tuple[EvidenceItem, ...]:
        rows = await retriever.retrieve(query, top_k=plan.top_k)
        return tuple(
            item
            for row in rows
            if (item := _multimodal_item(row)) is not None
            if _matches_scope(item, scope)
        )

    return _flatten(await asyncio.gather(*(one(query) for query in plan.queries)))


def _multimodal_item(row: Any) -> EvidenceItem | None:
    metadata = row.metadata if isinstance(getattr(row, "metadata", None), Mapping) else {}
    document_id = str(getattr(row, "doc_id", "") or metadata.get("document_id") or metadata.get("doc_id") or "").strip()
    source = str(metadata.get("source") or metadata.get("artifact_uri") or document_id).strip()
    content = str(getattr(row, "content", "") or "").strip()
    if not document_id or not source or not content:
        return None
    raw_modality = str(getattr(row, "modality", "text") or "text")
    modality = "image" if raw_modality in {"image", "chart"} else "table" if raw_modality == "table" else "text"
    image_id = str(metadata.get("image_id") or getattr(row, "id", "") or "").strip() if modality == "image" else None
    try:
        return EvidenceItem(
            content=content,
            source=source,
            document_id=document_id,
            version=_positive_int(metadata.get("version")),
            page=_positive_int(getattr(row, "page_number", None) or metadata.get("page")),
            chunk_id=_optional_text(metadata.get("chunk_id")),
            image_id=image_id or None,
            artifact_uri=_optional_text(metadata.get("artifact_uri") or metadata.get("original_image")),
            modality=modality,
            layer="evidence",
            acl_tags=frozenset(str(tag) for tag in metadata.get("acl_tags", ()) or ()),
            retriever="multimodal",
            score=_bounded_score(getattr(row, "score", None)),
        )
    except (TypeError, ValueError):
        return None


def _matches_scope(item: EvidenceItem, scope: AccessScope) -> bool:
    if scope.document_ids and item.document_id not in scope.document_ids:
        return False
    if scope.allowed_sources and item.source not in scope.allowed_sources:
        return False
    return not item.acl_tags or bool(item.acl_tags.intersection(scope.acl_tags))


def _flatten(groups: Sequence[Sequence[EvidenceItem]]) -> tuple[EvidenceItem, ...]:
    return tuple(item for group in groups for item in group)


def _optional_text(value: object) -> str | None:
    text = str(value or "").strip()
    return text or None


def _positive_int(value: object) -> int | None:
    try:
        number = int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    return number if number is not None and number > 0 else None


def _bounded_score(value: object) -> float | None:
    try:
        score = float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    return min(1.0, max(0.0, score)) if score is not None else None


__all__ = [
    "AdapterCallable",
    "CallableKnowledgeAdapter",
    "KnowledgeAdapter",
    "UnavailableKnowledgeAdapter",
    "UnavailableKnowledgeSourceError",
    "build_default_adapters",
]
