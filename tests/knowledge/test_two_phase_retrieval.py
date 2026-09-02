"""Graph retrieval may read what the document sources found -- under conditions.

`enhanced_graph.py` was unreachable in production for two independent reasons,
and fixing either alone leaves it unreachable:

1. `_run_graph_rag_impl` entered the enhanced branch only `if should_enhance and
   retrieved_docs`, and the one production caller had no documents to pass.
2. The orchestrator ran every source in one `gather`, so there was no point at
   which documents existed and graph retrieval had not started.

The second fix buys accuracy with latency -- a deferred source no longer overlaps
the others -- so the tests below pin that the cost is only paid when something
actually reads the prior evidence, and that it stays inside the retrieval stage's
budget.
"""

from __future__ import annotations

import asyncio

import pytest

from app.domain.contracts import EvidenceItem
from app.domain.knowledge import AccessScope, KnowledgeSourcePlan, KnowledgeStrategy
from app.knowledge.adapters import CallableKnowledgeAdapter
from app.knowledge.orchestrator import KnowledgeOrchestrator, discard_trace
from app.services.security.access_scope import DEFAULT_CONTEXT_FIELDS


def _scope() -> AccessScope:
    return AccessScope(
        tenant_id="alice",
        user_id="alice",
        role="viewer",
        allowed_sources=frozenset({"/uploads/alice/notes.pdf"}),
        allowed_fields=DEFAULT_CONTEXT_FIELDS,
    )


def _item(content: str, source: str, retriever: str) -> EvidenceItem:
    return EvidenceItem(
        content=content,
        source=source,
        document_id=source,
        version=1,
        retriever=retriever,
    )


def _strategy(*sources: str) -> KnowledgeStrategy:
    return KnowledgeStrategy(
        sources=tuple(
            KnowledgeSourcePlan(source=source, queries=("q3 revenue",), top_k=5, timeout_ms=5_000) for source in sources
        ),
        rewrite=False,
        rerank=False,
        rationale="test",
    )


class _RecordingGraphAdapter:
    """Stands in for `GraphKnowledgeAdapter`, recording what it was handed."""

    source = "graph"

    def __init__(self, *, wants: bool) -> None:
        self._wants = wants
        self.prior: tuple[EvidenceItem, ...] | None = None
        self.plain_calls = 0
        self.timeout_ms: int | None = None

    def wants_prior_evidence(self) -> bool:
        return self._wants

    async def retrieve(self, plan, scope):
        self.plain_calls += 1
        self.timeout_ms = plan.timeout_ms
        return ()

    async def retrieve_with_prior(self, plan, scope, prior):
        self.prior = prior
        self.timeout_ms = plan.timeout_ms
        return (_item("graph triple", "graph://q3", "graph"),)


def _adapters(graph: _RecordingGraphAdapter, *, vector_delay: float = 0.0):
    async def vector(plan, scope):
        if vector_delay:
            await asyncio.sleep(vector_delay)
        return (_item("Q3 revenue rose.", "/uploads/alice/notes.pdf", "vector"),)

    async def bm25(plan, scope):
        return (_item("revenue table", "/uploads/alice/notes.pdf", "bm25"),)

    return {
        "vector": CallableKnowledgeAdapter("vector", vector),
        "bm25": CallableKnowledgeAdapter("bm25", bm25),
        "graph": graph,
    }


def _run(adapters, strategy):
    orchestrator = KnowledgeOrchestrator(adapters=adapters)
    return asyncio.run(orchestrator.retrieve(strategy, _scope(), discard_trace))


def test_graph_receives_what_the_document_sources_found() -> None:
    graph = _RecordingGraphAdapter(wants=True)
    bundle = _run(_adapters(graph), _strategy("vector", "bm25", "graph"))

    assert graph.prior is not None
    assert {item.retriever for item in graph.prior} == {"vector", "bm25"}
    assert bundle.diagnostics["retrieval_phases"] == 2
    assert bundle.diagnostics["deferred_sources"] == ("graph",)


def test_a_source_that_would_not_use_it_keeps_its_concurrency() -> None:
    """The second phase costs latency; an adapter that ignores prior evidence
    must not pay for it. This is `GRAPH_RAG_ENHANCED=false`."""
    graph = _RecordingGraphAdapter(wants=False)
    bundle = _run(_adapters(graph), _strategy("vector", "bm25", "graph"))

    assert graph.prior is None
    assert graph.plain_calls == 1
    assert bundle.diagnostics["retrieval_phases"] == 1


def test_phase_two_inherits_the_remaining_stage_budget() -> None:
    """Otherwise two phases can take phase_one + phase_two and blow the stage
    ceiling, turning a sharper lookup into a degraded stage."""
    graph = _RecordingGraphAdapter(wants=True)
    orchestrator = KnowledgeOrchestrator(adapters=_adapters(graph, vector_delay=0.15))
    orchestrator._retrieval_budget_ms = 200

    asyncio.run(orchestrator.retrieve(_strategy("vector", "graph"), _scope(), discard_trace))

    assert graph.timeout_ms is not None
    assert graph.timeout_ms < 5_000


def test_outcomes_stay_aligned_with_their_plans() -> None:
    """Downstream zips plans against outcomes with strict=True and reads
    `plan.required` off the pair, so a reordering silently misattributes a
    failure to the wrong source."""
    graph = _RecordingGraphAdapter(wants=True)
    bundle = _run(_adapters(graph), _strategy("graph", "vector", "bm25"))

    statuses = bundle.diagnostics["source_status"]
    assert statuses["graph"] == "completed"
    assert statuses["vector"] == "completed"
    assert bundle.diagnostics["selected_sources"] == ("graph", "vector", "bm25")


def test_a_failed_source_contributes_no_prior_evidence() -> None:
    """A timed-out source has no results, not zero results -- feeding its silence
    to the quality estimator would read as a poor corpus."""

    async def broken(plan, scope):
        raise RuntimeError("vector store unavailable")

    graph = _RecordingGraphAdapter(wants=True)
    adapters = _adapters(graph)
    adapters["vector"] = CallableKnowledgeAdapter("vector", broken)

    _run(adapters, _strategy("vector", "bm25", "graph"))

    assert graph.prior is not None
    assert {item.retriever for item in graph.prior} == {"bm25"}


@pytest.mark.parametrize("enhanced", [True, False])
def test_the_real_graph_adapter_defers_only_in_enhanced_mode(monkeypatch, enhanced: bool) -> None:
    """The wiring under test is `GraphKnowledgeAdapter.wants_prior_evidence`
    reading the setting, not a test double agreeing with itself."""
    from app.core.config import get_settings
    from app.knowledge.adapters import GraphKnowledgeAdapter

    settings = get_settings()
    monkeypatch.setattr(settings, "graph_rag_enhanced", enhanced, raising=False)

    assert GraphKnowledgeAdapter().wants_prior_evidence() is enhanced
