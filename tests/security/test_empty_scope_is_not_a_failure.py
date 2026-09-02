"""A user who has uploaded nothing must get an answer, not a 500.

Found by walking the app as a new user: register, log in, ask one question ->
`POST /api/advanced-rag/query` returned 500. The pipeline raised
`RetrievalFailureError` from the `knowledge` stage with "All 2 retrieval attempts
failed. Failed retrievers: bm25, vector."

Nothing had failed. `KnowledgeOrchestrator._retrieve_source` *skips* the
document-backed sources when the caller's document scope is empty -- which is the
documented behaviour, and the whole point of keeping "empty scope" and "missing
scope" distinct (CLAUDE.md, User Data Isolation). But it reports that skip as
`source_status = "skipped"`, and `RAGAgentService.retrieve` judged the run with
`value != "completed"`, so a deliberate skip and a thrown vector store were the
same thing.

The degradation policy asks how much of the retrieval this run *attempted* came
back. A source that was never attempted belongs in neither the numerator nor the
denominator.
"""

from __future__ import annotations

import asyncio

import pytest

from app.agents.rag.service import NOT_ATTEMPTED, RAGAgentService, RetrievalFailureError
from app.domain.contracts import EvidenceItem, RouteDecision
from app.domain.knowledge import AccessScope, KnowledgeSourcePlan, KnowledgeStrategy
from app.knowledge.adapters import CallableKnowledgeAdapter
from app.orchestration.request import OrchestrationRequest, RequestActor
from app.services.security.access_scope import DEFAULT_CONTEXT_FIELDS


def _scope(*sources: str) -> AccessScope:
    return AccessScope(
        tenant_id="alice",
        user_id="alice",
        role="viewer",
        allowed_sources=frozenset(sources),
        allowed_fields=DEFAULT_CONTEXT_FIELDS,
    )


def _request() -> OrchestrationRequest:
    return OrchestrationRequest(
        question="what are the security risks of rag systems?",
        actor=RequestActor(user_id="alice", tenant_id="alice", role="viewer"),
    )


def _route() -> RouteDecision:
    return RouteDecision(
        route="vector",
        reason="test",
        confidence=1.0,
        requires_plan=False,
        allowed_capabilities=frozenset({"rag"}),
    )


def _strategy(*sources: str) -> KnowledgeStrategy:
    return KnowledgeStrategy(
        sources=tuple(
            KnowledgeSourcePlan(source=source, queries=("q",), top_k=4, timeout_ms=3_000, required=True)
            for source in sources
        ),
        rewrite=False,
        rerank=False,
        rationale="test",
    )


def _item(retriever: str) -> EvidenceItem:
    return EvidenceItem(
        content="evidence",
        source="https://example.com/a" if retriever == "web" else "/uploads/alice/notes.pdf",
        document_id="doc-1",
        version=1,
        retriever=retriever,
        # `evidence_is_authorized` exempts web and tool evidence by *layer*, not
        # by retriever name: they are not user documents and carry no owner.
        layer="web" if retriever == "web" else "evidence",
    )


def _service(**adapters) -> RAGAgentService:
    """Build a service whose named sources are the given fakes.

    `RAGAgentService` merges its argument *over* `build_default_adapters()`, so a
    source that is simply not named here keeps its real adapter and reaches real
    infrastructure. Passing `None` is how a test says "this deployment has no
    such store", which is what produces `AdapterNotConfigured`.
    """

    return RAGAgentService(
        adapters={
            name: (CallableKnowledgeAdapter(name, fn) if fn is not None else None) for name, fn in adapters.items()
        }
    )


def _retrieve(service: RAGAgentService, scope: AccessScope, *sources: str):
    return asyncio.run(service.retrieve(_request(), _route(), None, _strategy(*sources), scope))


async def _ok(plan, scope):
    return (_item(plan.source),)


async def _broken(plan, scope):
    raise RuntimeError("vector store unavailable")


class TestAnEmptyScopeReturnsQuietly:
    def test_a_user_with_no_documents_gets_a_bundle_not_an_exception(self) -> None:
        """The reported bug, at the layer that raised it."""
        context = _retrieve(_service(vector=_ok, bm25=_ok), _scope(), "vector", "bm25")

        assert context.evidence == ()

    def test_the_skip_reason_reaches_the_diagnostics(self) -> None:
        """`source_status` alone cannot distinguish the two, which is why the
        judgement was wrong; `source_error_type` is what makes it decidable."""
        context = _retrieve(_service(vector=_ok, bm25=_ok), _scope(), "vector", "bm25")

        assert context.diagnostics["source_status"] == {"vector": "skipped", "bm25": "skipped"}
        assert set(context.diagnostics["source_error_type"].values()) == {"EmptyAccessScope"}

    def test_web_still_runs_for_a_user_with_no_documents(self) -> None:
        """Web results are not user documents. An empty document scope drops the
        document-backed sources and nothing else."""
        context = _retrieve(_service(vector=_ok, bm25=_ok, web=_ok), _scope(), "vector", "bm25", "web")

        assert tuple(item.retriever for item in context.evidence) == ("web",)


class TestARealFailureStillRaises:
    def test_a_thrown_retriever_is_still_a_failure(self) -> None:
        """The fix must not make retrieval failures silent -- that would trade one
        bug for a worse one."""
        with pytest.raises(RetrievalFailureError):
            _retrieve(_service(vector=_broken, bm25=_broken), _scope("/uploads/alice/notes.pdf"), "vector", "bm25")

    def test_a_failure_alongside_a_scope_skip_is_still_judged(self) -> None:
        """Mixed case: the graph store is not configured (never attempted) and
        vector threw (attempted, failed). The verdict must come from vector.

        `graph=None` states the absence rather than relying on it. Leaving graph
        out of the map did not remove it -- the service merges over
        `build_default_adapters()` -- so the real adapter ran, reached whatever
        Neo4j the machine had, fell back to a real vector search on failure, and
        the source's verdict came out different on different machines. This test
        passed locally and failed on CI for that reason, which is the worst kind
        of test: one whose subject is the environment.
        """

        with pytest.raises(RetrievalFailureError):
            _retrieve(
                _service(vector=_broken, bm25=_broken, graph=None),
                _scope("/uploads/alice/notes.pdf"),
                "vector",
                "bm25",
                "graph",
            )

    def test_partial_success_is_still_acceptable(self) -> None:
        context = _retrieve(_service(vector=_ok, bm25=_broken), _scope("/uploads/alice/notes.pdf"), "vector", "bm25")

        assert tuple(item.retriever for item in context.evidence) == ("vector",)


def test_the_not_attempted_reasons_are_named_not_guessed() -> None:
    """Both are states the orchestrator creates deliberately; a typo here would
    silently restore the bug for one of them."""
    assert NOT_ATTEMPTED == frozenset({"EmptyAccessScope", "AdapterNotConfigured"})
