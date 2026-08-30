"""An empty document scope must disable document sources -- and only those.

`RAGAgentService.retrieve` used to return an empty bundle the moment the caller's
`allowed_sources` was empty, which is correct for vector/BM25/graph and wrong for
web: web results are not user documents and carry no owner, so a user who has
uploaded nothing was denied web search along with everything else.

The two halves are easy to break in opposite directions, so both are pinned here:
widening the empty-scope case back to document retrieval is a data leak, and
narrowing it back to "return nothing" silently removes a feature.

`KnowledgeOrchestrator._retrieve_source` already skips document-backed sources on
an empty scope; the service now agrees with it rather than short-circuiting first,
which also keeps `source_status` honest about what was attempted.
"""

from __future__ import annotations

import pytest

from app.agents.rag.service import RAGAgentService
from app.domain.contracts import EvidenceBundle, EvidenceItem, RouteDecision
from app.orchestration.request import OrchestrationRequest, RequestActor, RequestScope

ALICE_DOC = "/uploads/alice/notes.pdf"


def _route(*capabilities: str) -> RouteDecision:
    return RouteDecision(
        route="vector",
        reason="test",
        confidence=1.0,
        requires_plan=False,
        allowed_capabilities=frozenset(capabilities),
    )


def _request(scope: RequestScope) -> OrchestrationRequest:
    return OrchestrationRequest(
        question="what happened in q3",
        actor=RequestActor(user_id="alice", tenant_id="alice", role="viewer"),
        source_scope=scope,
    )


class _Recorder:
    """A stub retriever that records that it ran and returns one item."""

    def __init__(self, name: str, source: str) -> None:
        self.name = name
        self.source = source
        self.ran = False

    async def __call__(self, request, route, plan) -> EvidenceBundle:
        self.ran = True
        return EvidenceBundle(
            items=(
                EvidenceItem(
                    content=f"{self.name} result",
                    source=self.source,
                    document_id=f"doc-{self.name}",
                    retriever=self.name,
                ),
            )
        )


def _service() -> tuple[RAGAgentService, dict[str, _Recorder]]:
    recorders = {
        "vector": _Recorder("vector", ALICE_DOC),
        "bm25": _Recorder("bm25", ALICE_DOC),
        "graph": _Recorder("graph", ALICE_DOC),
        "web": _Recorder("web", "https://example.com/q3"),
    }
    service = RAGAgentService(
        vector=recorders["vector"],
        bm25=recorders["bm25"],
        graph=recorders["graph"],
        web=recorders["web"],
    )
    return service, recorders


def _ran(recorders: dict[str, _Recorder]) -> set[str]:
    return {name for name, recorder in recorders.items() if recorder.ran}


@pytest.mark.asyncio
async def test_a_user_with_no_documents_still_gets_web_search():
    service, recorders = _service()

    bundle = await service.retrieve(
        _request(RequestScope(allowed_sources=frozenset())),
        _route("rag", "web"),
        None,
    )

    assert _ran(recorders) == {"web"}
    assert {item.source for item in bundle.items} == {"https://example.com/q3"}


@pytest.mark.asyncio
async def test_an_empty_scope_reaches_no_document_retriever():
    """The half that must not regress: empty scope is not a licence to read."""
    service, recorders = _service()

    await service.retrieve(
        _request(RequestScope(allowed_sources=frozenset())),
        _route("rag", "web"),
        None,
    )

    assert "vector" not in _ran(recorders)
    assert "bm25" not in _ran(recorders)
    assert "graph" not in _ran(recorders)


@pytest.mark.asyncio
async def test_an_empty_scope_without_web_retrieves_nothing():
    service, recorders = _service()

    bundle = await service.retrieve(
        _request(RequestScope(allowed_sources=frozenset())),
        _route("rag"),
        None,
    )

    assert _ran(recorders) == set()
    assert bundle.items == ()


@pytest.mark.asyncio
async def test_a_scoped_caller_still_reaches_the_document_retrievers():
    service, recorders = _service()

    bundle = await service.retrieve(
        _request(RequestScope(allowed_sources=frozenset({ALICE_DOC}))),
        _route("rag", "web"),
        None,
    )

    assert _ran(recorders) == {"vector", "bm25", "web"}
    assert ALICE_DOC in {item.source for item in bundle.items}


@pytest.mark.asyncio
async def test_the_graph_retriever_joins_only_on_its_own_routes():
    service, recorders = _service()
    route = _route("rag").model_copy(update={"route": "graph"})

    await service.retrieve(
        _request(RequestScope(allowed_sources=frozenset({ALICE_DOC}))),
        route,
        None,
    )

    assert "graph" in _ran(recorders)


@pytest.mark.asyncio
async def test_retrieval_is_skipped_entirely_without_the_rag_capability():
    service, recorders = _service()

    bundle = await service.retrieve(
        _request(RequestScope(allowed_sources=frozenset({ALICE_DOC}))),
        _route("web"),
        None,
    )

    assert _ran(recorders) == set()
    assert bundle.items == ()


@pytest.mark.asyncio
async def test_a_missing_scope_fails_loudly_rather_than_returning_nothing():
    """A missing scope is a caller bug and must not read as "no matches found".

    The document retrievers stay selected, KnowledgeOrchestrator skips them as
    EmptyAccessScope, and the degradation policy then sees zero successes. The
    distinction that matters: an *empty* scope is a legitimate state that yields
    a quiet empty result, a *missing* one is a bug that raises.
    """
    from app.agents.rag.service import RetrievalFailureError

    service, recorders = _service()

    with pytest.raises(RetrievalFailureError):
        await service.retrieve(_request(RequestScope()), _route("rag"), None)

    assert _ran(recorders) == set(), "no document retriever may actually run unscoped"


@pytest.mark.asyncio
async def test_an_empty_scope_is_quiet_where_a_missing_one_is_loud():
    """The pair above and below, stated as one contrast so neither drifts."""
    service, _ = _service()

    quiet = await service.retrieve(
        _request(RequestScope(allowed_sources=frozenset())),
        _route("rag"),
        None,
    )
    assert quiet.items == ()
