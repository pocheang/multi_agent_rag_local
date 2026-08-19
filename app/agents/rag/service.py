"""Concurrent typed retrieval adapter over the established local retrievers."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Mapping, Sequence

from app.agents.rag.fusion import fuse_evidence
from app.domain.contracts import EvidenceBundle, EvidenceItem, RouteDecision, TaskPlan
from app.domain.events import ExecutionEvent
from app.orchestration.request import OrchestrationRequest

TypedRetriever = Callable[[OrchestrationRequest, RouteDecision, TaskPlan | None], Awaitable[EvidenceBundle]]
DegradationReporter = Callable[[ExecutionEvent], Awaitable[None]]


class RetrieverSoftFailure(RuntimeError):
    """A legacy retriever returned an explicit failure payload."""


class RAGAgentService:
    """Run enabled vector, graph, and web retrievers concurrently, then fuse their evidence."""

    def __init__(
        self,
        *,
        vector: TypedRetriever | None = None,
        bm25: TypedRetriever | None = None,
        graph: TypedRetriever | None = None,
        web: TypedRetriever | None = None,
        report_degradation: DegradationReporter | None = None,
    ) -> None:
        self._vector = vector or _vector_retrieve
        self._bm25 = bm25 or _bm25_retrieve
        self._graph = graph or _graph_retrieve
        self._web = web or _web_retrieve
        self._report_degradation = report_degradation or _discard_event

    def set_degradation_reporter(self, reporter: DegradationReporter) -> None:
        """Bind the engine publisher after typed services are assembled."""
        self._report_degradation = reporter

    async def retrieve(
        self,
        request: OrchestrationRequest,
        route: RouteDecision,
        plan: TaskPlan | None,
    ) -> EvidenceBundle:
        """Retrieve every permitted source for each retrieval-enabled planned task."""
        if "rag" not in route.allowed_capabilities:
            return EvidenceBundle()
        if request.source_scope.allowed_sources is not None and not request.source_scope.allowed_sources:
            return EvidenceBundle()
        retrievers = self._enabled_retrievers(route)
        requests = _retrieval_requests(request, plan, len(retrievers))
        jobs = [
            (name, retriever, planned_request)
            for planned_request, max_retrievals in requests
            for name, retriever in retrievers[:max_retrievals]
        ]
        results = await asyncio.gather(
            *(retriever(planned_request, route, plan) for _, retriever, planned_request in jobs),
            return_exceptions=True,
        )
        bundles: list[EvidenceBundle] = []
        failed_retrievers: list[str] = []
        for (name, _, _), result in zip(jobs, results, strict=True):
            if isinstance(result, BaseException):
                failed_retrievers.append(name)
                await self._report_degradation(
                    ExecutionEvent(stage="rag", status="skipped", message=f"{name}: {type(result).__name__}")
                )
                continue
            bundles.append(result)

        # If all retrievers failed, raise an error instead of returning empty bundle
        if not bundles and jobs:
            raise RuntimeError(f"All {len(jobs)} retrieval attempts failed: {', '.join(failed_retrievers)}")

        return fuse_evidence(bundles)

    def _enabled_retrievers(self, route: RouteDecision) -> tuple[tuple[str, TypedRetriever], ...]:
        retrievers: list[tuple[str, TypedRetriever]] = [("vector", self._vector), ("bm25", self._bm25)]
        if route.intent == "hybrid":
            retrievers.append(("graph", self._graph))
        if "web" in route.allowed_capabilities:
            retrievers.append(("web", self._web))
        return tuple(retrievers)


def _retrieval_requests(
    request: OrchestrationRequest, plan: TaskPlan | None, available_retrievers: int
) -> tuple[tuple[OrchestrationRequest, int], ...]:
    if plan is None:
        return ((request, available_retrievers),)
    return tuple(
        (request.model_copy(update={"question": task.prompt}), min(task.budget.max_retrievals, available_retrievers))
        for task in plan.tasks
        if task.retrieval_required and task.budget.max_retrievals > 0
    )


async def _discard_event(event: ExecutionEvent) -> None:
    """Keep degradation optional until orchestration supplies a publisher."""
    del event


async def _bm25_retrieve(
    request: OrchestrationRequest,
    route: RouteDecision,
    plan: TaskPlan | None,
) -> EvidenceBundle:
    del route, plan
    from app.retrievers.bm25_retriever import bm25_search

    records = await asyncio.to_thread(
        bm25_search,
        request.question,
        allowed_sources=list(request.source_scope.allowed_sources) if request.source_scope.allowed_sources else None,
    )
    return _bundle_from_bm25_records(records)


async def _vector_retrieve(
    request: OrchestrationRequest,
    route: RouteDecision,
    plan: TaskPlan | None,
) -> EvidenceBundle:
    del route, plan
    from app.retrievers.vector_store import similarity_search

    matches = await asyncio.to_thread(
        similarity_search,
        request.question,
        allowed_sources=list(request.source_scope.allowed_sources) if request.source_scope.allowed_sources else None,
        require_source_filter=False,
    )
    return _bundle_from_vector_matches(matches)


async def _graph_retrieve(
    request: OrchestrationRequest,
    route: RouteDecision,
    plan: TaskPlan | None,
) -> EvidenceBundle:
    del route, plan
    from app.agents.rag.graph import run_graph_rag

    result = await asyncio.to_thread(
        run_graph_rag,
        request.question,
        allowed_sources=list(request.source_scope.allowed_sources) if request.source_scope.allowed_sources else None,
        agent_class=request.source_scope.agent_class_hint,
    )
    return _bundle_from_legacy_payload(result, "graph", fallback_document_id=f"graph:{request.question}")


async def _web_retrieve(
    request: OrchestrationRequest,
    route: RouteDecision,
    plan: TaskPlan | None,
) -> EvidenceBundle:
    del route, plan
    from app.agents.rag.web import run_web_research

    result = await asyncio.to_thread(
        run_web_research,
        request.question,
        user_id=request.actor.user_id if request.actor else None,
        session_id=request.session_id,
    )
    return _bundle_from_legacy_payload(result, "web")


def _bundle_from_legacy_payload(
    payload: object,
    retriever: str,
    *,
    fallback_document_id: str | None = None,
) -> EvidenceBundle:
    if not isinstance(payload, Mapping):
        return EvidenceBundle()
    error = str(payload.get("error") or "").strip()
    if error:
        raise RetrieverSoftFailure(error)
    citations = payload.get("citations")
    if isinstance(citations, Sequence) and not isinstance(citations, str | bytes):
        items = tuple(
            item
            for citation in citations
            if isinstance(citation, Mapping)
            if (item := _item_from_legacy_citation(citation, retriever)) is not None
        )
        if items:
            return EvidenceBundle(items=items)
    if retriever == "graph":
        context = str(payload.get("context") or "").strip()
        if context and fallback_document_id:
            return EvidenceBundle(
                items=(
                    EvidenceItem(
                        content=context,
                        source="knowledge_graph",
                        document_id=fallback_document_id,
                        retriever="graph",
                        score=_score(payload.get("graph_signal_score")),
                    ),
                )
            )
    return EvidenceBundle()


def _item_from_legacy_citation(citation: Mapping[object, object], retriever: str) -> EvidenceItem | None:
    metadata = citation.get("metadata")
    metadata = metadata if isinstance(metadata, Mapping) else {}
    source = _legacy_text(citation, metadata, "source", "url")
    document_id = _legacy_text(citation, metadata, "document_id", "doc_id", "id") or source
    content = _legacy_text(citation, metadata, "content", "snippet", "text")
    if not source or not document_id or not content:
        return None
    score = _legacy_value(citation, metadata, "score", "rerank_score", "hybrid_score", "dense_score", "bm25_score")
    try:
        return EvidenceItem(
            content=content,
            source=source,
            document_id=document_id,
            page=_positive_page(_legacy_value(citation, metadata, "page")),
            retriever=retriever,
            score=_score(score),
        )
    except (TypeError, ValueError):
        return None


def _bundle_from_vector_matches(matches: object) -> EvidenceBundle:
    if not isinstance(matches, Sequence) or isinstance(matches, str | bytes):
        return EvidenceBundle()
    items: list[EvidenceItem] = []
    for match in matches:
        if not isinstance(match, tuple) or len(match) != 2:
            continue
        document, relevance = match
        metadata = getattr(document, "metadata", {})
        metadata = metadata if isinstance(metadata, Mapping) else {}
        source = _legacy_text({}, metadata, "source", "url")
        document_id = _legacy_text({}, metadata, "document_id", "doc_id", "id") or source
        content = str(getattr(document, "page_content", "") or "").strip()
        if not source or not document_id or not content:
            continue
        try:
            items.append(
                EvidenceItem(
                    content=content,
                    source=source,
                    document_id=document_id,
                    page=_positive_page(_legacy_value({}, metadata, "page")),
                    retriever="vector",
                    score=_score(relevance),
                )
            )
        except (TypeError, ValueError):
            continue
    return EvidenceBundle(items=tuple(items))


def _bundle_from_bm25_records(records: object) -> EvidenceBundle:
    if not isinstance(records, Sequence) or isinstance(records, str | bytes):
        return EvidenceBundle()
    items: list[EvidenceItem] = []
    for record in records:
        if not isinstance(record, Mapping):
            continue
        metadata = record.get("metadata")
        metadata = metadata if isinstance(metadata, Mapping) else {}
        source = _legacy_text(record, metadata, "source", "url")
        document_id = _legacy_text(record, metadata, "id", "document_id", "doc_id") or source
        content = _legacy_text(record, metadata, "text", "content", "snippet")
        if not source or not document_id or not content:
            continue
        try:
            items.append(
                EvidenceItem(
                    content=content,
                    source=source,
                    document_id=document_id,
                    page=_positive_page(_legacy_value(record, metadata, "page")),
                    retriever="bm25",
                    score=_score(_legacy_value(record, metadata, "bm25_score", "score")),
                )
            )
        except (TypeError, ValueError):
            continue
    return EvidenceBundle(items=tuple(items))


def _legacy_text(
    record: Mapping[object, object], metadata: Mapping[object, object], *names: str
) -> str:
    value = _legacy_value(record, metadata, *names)
    return str(value or "").strip()


def _legacy_value(record: Mapping[object, object], metadata: Mapping[object, object], *names: str) -> object:
    for name in names:
        value = record.get(name)
        if value is not None:
            return value
        value = metadata.get(name)
        if value is not None:
            return value
    return None


def _positive_page(value: object) -> int | None:
    try:
        page = int(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    return page if page and page > 0 else None


def _score(value: object) -> float | None:
    try:
        score = float(value) if value is not None else None
    except (TypeError, ValueError):
        return None
    return min(1.0, max(0.0, score)) if score is not None else None
