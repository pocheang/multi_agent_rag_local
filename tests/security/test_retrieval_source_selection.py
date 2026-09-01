"""An empty document scope must disable document sources -- and only those.

Retrieval used to return an empty bundle the moment the caller's
`allowed_sources` was empty, which is correct for vector/BM25/graph and wrong for
web: web results are not user documents and carry no owner, so a user who had
uploaded nothing was denied web search along with everything else.

The two halves are easy to break in opposite directions, so both are pinned here:
widening the empty-scope case back to document retrieval is a data leak, and
narrowing it back to "return nothing" silently removes a feature.

Since 2026-08-30 the check lives in exactly one place --
`KnowledgeOrchestrator._retrieve_source` -- because `RAGAgentService` no longer
selects sources at all. The *empty vs missing* scope distinction moved upstream
with it: `AccessScope` always carries a frozenset, and a missing scope now fails
at the resolver and at `similarity_search`/`bm25_search`, which
`test_retrieval_isolation.py` pins.
"""

from __future__ import annotations

import pytest

from app.agents.rag.service import RAGAgentService
from app.domain.contracts import EvidenceItem, RouteDecision
from app.domain.knowledge import AccessScope, KnowledgeSourcePlan, KnowledgeStrategy
from app.knowledge.adapters import CallableKnowledgeAdapter
from app.orchestration.request import OrchestrationRequest, RequestActor
from app.services.security.access_scope import DEFAULT_CONTEXT_FIELDS

ALICE_DOC = "/uploads/alice/notes.pdf"


def _route(*capabilities: str) -> RouteDecision:
    return RouteDecision(
        route="vector",
        reason="test",
        confidence=1.0,
        requires_plan=False,
        allowed_capabilities=frozenset(capabilities),
    )


def _request() -> OrchestrationRequest:
    return OrchestrationRequest(
        question="what happened in q3",
        actor=RequestActor(user_id="alice", tenant_id="alice", role="viewer"),
    )


def _scope(*sources: str) -> AccessScope:
    return AccessScope(
        tenant_id="alice",
        user_id="alice",
        role="viewer",
        allowed_sources=frozenset(sources),
        allowed_fields=DEFAULT_CONTEXT_FIELDS,
    )


class _Recorder:
    """An adapter stub that records that it ran and returns one item."""

    def __init__(self, name: str, source: str) -> None:
        self.name = name
        self.source = source
        self.ran = False

    async def retrieve(self, plan, scope) -> tuple[EvidenceItem, ...]:
        del plan, scope
        self.ran = True
        return (
            EvidenceItem(
                content=f"{self.name} result",
                source=self.source,
                document_id=f"doc-{self.name}",
                version=1,
                retriever=self.name,
                layer="web" if self.name == "web" else "evidence",
            ),
        )


def _service() -> tuple[RAGAgentService, dict[str, _Recorder]]:
    recorders = {
        "vector": _Recorder("vector", ALICE_DOC),
        "bm25": _Recorder("bm25", ALICE_DOC),
        "graph": _Recorder("graph", ALICE_DOC),
        "web": _Recorder("web", "https://example.com/q3"),
    }
    adapters = {name: CallableKnowledgeAdapter(name, recorder.retrieve) for name, recorder in recorders.items()}
    return RAGAgentService(adapters=adapters), recorders


def _strategy(*sources: str) -> KnowledgeStrategy:
    return KnowledgeStrategy(
        sources=tuple(
            KnowledgeSourcePlan(
                source=source,
                queries=("what happened in q3",),
                top_k=6,
                timeout_ms=5_000,
                required=source in {"vector", "bm25"},
            )
            for source in sources
        ),
        rewrite=False,
        rationale="test",
    )


def _ran(recorders: dict[str, _Recorder]) -> set[str]:
    return {name for name, recorder in recorders.items() if recorder.ran}


@pytest.mark.asyncio
async def test_a_user_with_no_documents_still_gets_web_search():
    service, recorders = _service()

    context = await service.retrieve(
        _request(), _route("rag", "web"), None, _strategy("vector", "bm25", "web"), _scope()
    )

    assert _ran(recorders) == {"web"}
    assert {item.source for item in context.evidence} == {"https://example.com/q3"}


@pytest.mark.asyncio
async def test_an_empty_scope_reaches_no_document_retriever():
    service, recorders = _service()

    await service.retrieve(
        _request(), _route("rag", "web"), None, _strategy("vector", "bm25", "graph", "web"), _scope()
    )

    assert "vector" not in _ran(recorders)
    assert "bm25" not in _ran(recorders)
    assert "graph" not in _ran(recorders)


@pytest.mark.asyncio
async def test_an_empty_scope_without_web_returns_quietly_and_says_why():
    """A user who has uploaded nothing must get an answer, not an exception.

    This test used to assert the opposite -- that an empty scope with no web
    source should raise, on the grounds that returning quietly reads to the
    caller as "no matches found" when in truth every source was skipped. Walking
    the app as a new user showed what that costs: register, log in, ask one
    question, and `POST /api/advanced-rag/query` answers 500. An empty document
    scope is the *normal* state of every new account, and CLAUDE.md's User Data
    Isolation contract has always said empty returns quietly while only a
    *missing* scope raises.

    The concern behind the old assertion was real, and it is answered by the
    diagnostics rather than by an exception: `source_error_type` tells the caller
    that these sources were never attempted and why. Distinguishing "nothing ran"
    from "nothing matched" is a reporting job, not a reason to fail the request.
    See tests/security/test_empty_scope_is_not_a_failure.py.
    """
    service, _ = _service()

    context = await service.retrieve(_request(), _route("rag"), None, _strategy("vector", "bm25"), _scope())

    assert context.evidence == ()
    assert set(context.diagnostics["source_error_type"].values()) == {"EmptyAccessScope"}


@pytest.mark.asyncio
async def test_a_scoped_caller_still_reaches_the_document_retrievers():
    service, recorders = _service()

    context = await service.retrieve(_request(), _route("rag"), None, _strategy("vector", "bm25"), _scope(ALICE_DOC))

    assert _ran(recorders) == {"vector", "bm25"}
    assert {item.source for item in context.evidence} == {ALICE_DOC}


@pytest.mark.asyncio
async def test_only_the_strategy_decides_which_sources_run():
    """Execution runs what it was handed. It used to override the strategy with
    a route-derived set of its own, which is how `memory`, `wiki` and
    `multimodal` stayed unreachable however the Knowledge Agent chose them."""
    service, recorders = _service()

    await service.retrieve(_request(), _route("rag"), None, _strategy("vector"), _scope(ALICE_DOC))

    assert _ran(recorders) == {"vector"}


@pytest.mark.asyncio
async def test_retrieval_is_skipped_entirely_without_the_rag_capability():
    service, recorders = _service()

    context = await service.retrieve(_request(), _route("web"), None, _strategy("vector", "bm25"), _scope(ALICE_DOC))

    assert _ran(recorders) == set()
    assert context.evidence == ()
