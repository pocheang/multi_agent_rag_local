"""Typed adapters over existing knowledge retrieval implementations."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from typing import Protocol

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
        "wiki": CallableKnowledgeAdapter("wiki", _retrieve_wiki),
        "web": CallableKnowledgeAdapter("web", _retrieve_web),
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
        return await retriever.retrieve_evidence(query, scope, top_k=plan.top_k)

    return _flatten(await asyncio.gather(*(one(query) for query in plan.queries)))


async def _retrieve_wiki(plan: KnowledgeSourcePlan, scope: AccessScope) -> tuple[EvidenceItem, ...]:
    from app.wiki.store import WikiStore

    store = await asyncio.to_thread(WikiStore)

    async def one(query: str) -> tuple[EvidenceItem, ...]:
        rows = await asyncio.to_thread(store.search, query, scope, top_k=plan.top_k)
        output: list[EvidenceItem] = []
        for article, score in rows:
            wiki_uri = f"wiki://{article.tenant_id}/{article.article_id}/v{article.version}"
            for reference in article.source_references:
                output.append(
                    EvidenceItem(
                        content=f"# {article.title}\n\n{article.content}",
                        source=reference.source,
                        document_id=reference.document_id,
                        version=reference.document_version,
                        page=reference.page,
                        chunk_id=reference.chunk_id,
                        image_id=reference.image_id,
                        artifact_uri=wiki_uri,
                        modality="image" if reference.image_id else "text",
                        layer="knowledge",
                        acl_tags=reference.acl_tags,
                        retriever=f"wiki:v{article.version}",
                        score=score,
                    )
                )
        return tuple(output[: plan.top_k])

    return _flatten(await asyncio.gather(*(one(query) for query in plan.queries)))


def _flatten(groups: Sequence[Sequence[EvidenceItem]]) -> tuple[EvidenceItem, ...]:
    return tuple(item for group in groups for item in group)


__all__ = [
    "AdapterCallable",
    "CallableKnowledgeAdapter",
    "KnowledgeAdapter",
    "UnavailableKnowledgeAdapter",
    "UnavailableKnowledgeSourceError",
    "build_default_adapters",
]
