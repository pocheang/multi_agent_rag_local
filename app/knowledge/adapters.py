"""Typed adapters over existing knowledge retrieval implementations."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Sequence
from itertools import zip_longest
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


class PriorEvidenceAdapter(Protocol):
    """An adapter whose retrieval is sharpened by what the other sources found.

    The orchestrator runs sources concurrently, which is the right default: they
    are independent.  A source that implements this protocol declares it is not,
    and the orchestrator gives it a second phase after the independent ones have
    returned.  That costs its duration on the critical path instead of hiding it
    under the others, so an adapter must report `wants_prior_evidence` False
    whenever the prior evidence would not change what it does -- paying for a
    phase that changes nothing is the whole reason this is opt-in per call rather
    than a static property of the source.

    `prior` is evidence this system retrieved under the caller's own scope, and it
    must not be used to widen retrieval -- only to tune it.  See
    `GraphKnowledgeAdapter`.
    """

    source: KnowledgeSource

    def wants_prior_evidence(self) -> bool: ...

    async def retrieve_with_prior(
        self,
        plan: KnowledgeSourcePlan,
        scope: AccessScope,
        prior: tuple[EvidenceItem, ...],
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
        "graph": GraphKnowledgeAdapter(),
        "multimodal": CallableKnowledgeAdapter("multimodal", _retrieve_multimodal),
        "wiki": CallableKnowledgeAdapter("wiki", _retrieve_wiki),
        "memory": CallableKnowledgeAdapter("memory", _retrieve_memory),
        "web": CallableKnowledgeAdapter("web", _retrieve_web),
        "tool": UnavailableKnowledgeAdapter("tool", "tool retrieval is delegated to the governed Tool Agent"),
    }


async def _retrieve_vector(plan: KnowledgeSourcePlan, scope: AccessScope) -> tuple[EvidenceItem, ...]:
    from app.retrievers.stores.vector import OwnerScope, similarity_search

    allowed = sorted(scope.allowed_sources)
    owner = OwnerScope.from_access_scope(scope)

    async def one(query: str) -> tuple[EvidenceItem, ...]:
        # require_source_filter stays at its default. `allowed` is always a list
        # here (an empty one returns no results), so disabling the guard only
        # ever made a future edit dangerous.
        matches = await asyncio.to_thread(
            similarity_search,
            query,
            plan.top_k,
            allowed,
            True,
            owner,
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


class GraphKnowledgeAdapter:
    """Graph retrieval, optionally tuned by what the document sources found.

    Two things are separable here and were previously confused.  The *enhanced
    lookup* (entity normalization, alias matching, relation weighting) needs no
    documents.  The *adaptive result limits* -- and the decision to skip a graph
    lookup whose source documents are too poor to have produced a trustworthy
    graph -- are estimated from the documents, which only exist after the other
    sources have run.

    So this adapter asks for a second phase only when enhanced mode is on.  With
    `GRAPH_RAG_ENHANCED` off, the prior evidence has no reader and the adapter
    stays in phase one, where graph retrieval overlaps everything else exactly as
    before.

    **Prior evidence tunes; it never widens.** What crosses into
    `run_graph_rag` is a quality *score* over the retrieved text plus its page
    and format metadata; `run_graph_rag_with_pdf_context` does not read entities
    out of the documents to query with, and `allowed_sources`/`owner` are still
    the caller's, resolved by `privacy_permission`.  A document that argues for
    its own importance can therefore buy itself a larger `max_neighbors` and
    nothing else.  Keep it that way: letting document text choose which entities
    to look up would make retrieved content steer retrieval, and the answer to
    "who wrote this document" is not always "the person asking".
    """

    source: KnowledgeSource = "graph"

    def wants_prior_evidence(self) -> bool:
        from app.core.config import get_settings

        return bool(get_settings().graph_rag_enhanced)

    async def retrieve(self, plan: KnowledgeSourcePlan, scope: AccessScope) -> tuple[EvidenceItem, ...]:
        return await self.retrieve_with_prior(plan, scope, ())

    async def retrieve_with_prior(
        self,
        plan: KnowledgeSourcePlan,
        scope: AccessScope,
        prior: tuple[EvidenceItem, ...],
    ) -> tuple[EvidenceItem, ...]:
        from app.agents.rag.graph import run_graph_rag
        from app.retrievers.stores.vector import OwnerScope

        allowed = sorted(scope.allowed_sources)
        owner = OwnerScope.from_access_scope(scope)
        documents = _as_quality_documents(prior)

        async def one(query: str) -> tuple[EvidenceItem, ...]:
            result = await asyncio.to_thread(
                run_graph_rag,
                query,
                allowed,
                None,
                documents,
                None,
                owner=owner,
            )
            bundle = bundle_from_legacy_payload(result, "graph", fallback_document_id=f"graph:{query}")
            return tuple(item.model_copy(update={"modality": "graph"}) for item in bundle.items)

        return _flatten(await asyncio.gather(*(one(query) for query in plan.queries)))


def _as_quality_documents(items: tuple[EvidenceItem, ...]) -> list[dict] | None:
    """Shape evidence into what the PDF quality analyzer reads, and nothing more.

    Only text evidence: the analyzer scores prose structure and density, so an
    image caption or a graph triple would score as a poor document and drag the
    estimate down for reasons that say nothing about document quality.
    """
    documents = [
        {
            "content": item.content,
            "metadata": {"page": item.page, "source": item.source},
        }
        for item in items
        if item.modality == "text" and item.layer == "evidence"
    ]
    return documents or None


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


async def _retrieve_memory(plan: KnowledgeSourcePlan, scope: AccessScope) -> tuple[EvidenceItem, ...]:
    from app.memory.long_term import GBrainLongTermMemory

    provider = GBrainLongTermMemory()

    async def one(query: str) -> tuple[EvidenceItem, ...]:
        memories = await provider.search(query, scope, plan.top_k)
        return tuple(
            EvidenceItem(
                content=memory.content,
                source=f"memory://{scope.tenant_id}/{scope.user_id}/{memory.memory_id}",
                document_id=f"memory:{memory.memory_id}",
                version=1,
                modality="text",
                layer="memory",
                retriever="gbrain",
                score=1.0 / rank,
            )
            for rank, memory in enumerate(memories, start=1)
        )

    return _flatten(await asyncio.gather(*(one(query) for query in plan.queries)))


def _flatten(groups: Sequence[Sequence[EvidenceItem]]) -> tuple[EvidenceItem, ...]:
    """Interleave the per-query result lists instead of concatenating them.

    Every adapter fans out over ``plan.queries`` and hands the combined list to
    one source slot, and ``reciprocal_rank_fuse`` scores by *position in that
    list*. Concatenating meant the second query's rank-1 hit arrived at position
    ``top_k + 1`` and was scored as a mediocre result -- a systematic penalty on
    every query but the first, growing with the number of queries.

    This is not a latent bug waiting on sub-queries. ``QUERY_REWRITE_ENABLED``
    defaults true and the rule rewriter needs no LLM, so requests already arrive
    here with more than one query -- measured: a Chinese question containing
    punctuation yields 2-3, a multi-word English one yields 3, and a short
    punctuation-free Chinese question yields 1, where this was a no-op.

    Round-robin restores the intent: position in the fused list reflects rank
    *within* a query. An item several queries return still accumulates one RRF
    contribution per query, which is the agreement signal worth keeping.
    """

    ordered: list[EvidenceItem] = []
    for row in zip_longest(*groups, fillvalue=None):
        ordered.extend(item for item in row if item is not None)
    return tuple(ordered)


__all__ = [
    "AdapterCallable",
    "CallableKnowledgeAdapter",
    "GraphKnowledgeAdapter",
    "KnowledgeAdapter",
    "PriorEvidenceAdapter",
    "UnavailableKnowledgeAdapter",
    "UnavailableKnowledgeSourceError",
    "build_default_adapters",
]
