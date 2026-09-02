"""One user's query must never reach another user's chunks in the vector store.

Runs Alice's and Bob's documents through a fake Chroma collection that honours
the `filter` argument exactly the way Chroma does, so the assertions are about
what the retrieval layer *asks for*, not about embedding quality.

The output-stage filter (app/privacy/dlp.py) already drops Bob's chunks before
they reach the model, so these tests are not about the answer text. They are
about the retrieval boundary: when Alice's top-k is computed over Bob's corpus,
Alice's own chunks get crowded out and she is told nothing was found, and the
candidate counts that leak back in diagnostics reveal how many documents Bob
has. See P0-1 in
docs/superpowers/plans/2026-08-29-user-data-isolation.md.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.domain.knowledge import AccessScope, KnowledgeSourcePlan, KnowledgeStrategy
from app.services.security.access_scope import DEFAULT_CONTEXT_FIELDS

ALICE_DOC = "/uploads/alice/notes.pdf"
BOB_DOC = "/uploads/bob/salary.pdf"
SHARED_DOC = "/docs/handbook.pdf"

_CORPUS = [
    {
        "source": ALICE_DOC,
        "owner_user_id": "alice",
        "tenant_id": "alice",
        "visibility": "private",
        "document_id": "doc-alice",
        "text": "alice quarterly notes",
    },
    {
        "source": BOB_DOC,
        "owner_user_id": "bob",
        "tenant_id": "bob",
        "visibility": "private",
        "document_id": "doc-bob",
        "text": "bob compensation review",
    },
    {
        "source": SHARED_DOC,
        "owner_user_id": "",
        "tenant_id": "shared",
        "visibility": "private",
        "document_id": "doc-shared",
        "text": "shared handbook quarterly policy",
    },
]


def _matches(row: dict, clause: dict) -> bool:
    """Evaluate the subset of Chroma's `where` grammar this module emits."""
    for key, condition in clause.items():
        if key == "$and":
            if not all(_matches(row, part) for part in condition):
                return False
        elif key == "$or":
            if not any(_matches(row, part) for part in condition):
                return False
        elif "$in" in condition:
            if row.get(key, "") not in condition["$in"]:
                return False
        elif "$eq" in condition:
            if row.get(key, "") != condition["$eq"]:
                return False
        else:
            raise AssertionError(f"unhandled filter operator in {condition!r}")
    return True


class _Document:
    """Stands in for langchain_core.documents.Document."""

    def __init__(self, page_content: str, metadata: dict[str, Any]) -> None:
        self.page_content = page_content
        self.metadata = metadata


class _FakeCollection:
    """Applies a Chroma `{"source": {"$in": [...]}}` filter over an in-memory corpus."""

    def __init__(self, rows: list[dict] | None = None) -> None:
        self.calls: list[dict[str, Any] | None] = []
        self.rows = [dict(row) for row in (rows if rows is not None else _CORPUS)]

    def similarity_search_with_relevance_scores(self, query: str, k: int = 4, filter: dict | None = None):
        del query
        self.calls.append(filter)
        rows = self.rows if filter is None else [row for row in self.rows if _matches(row, filter)]
        return [
            (
                _Document(
                    row["text"],
                    # Only the keys the row actually has, so a legacy chunk with
                    # no owner metadata stays legacy -- Chroma stores no key at
                    # all in that case, and `$eq` does not match an absent key.
                    {key: value for key, value in row.items() if key != "text"}
                    | {"chunk_id": f"chunk-{row['document_id']}"},
                ),
                0.9,
            )
            for row in rows[:k]
        ]


@pytest.fixture
def collection(monkeypatch) -> _FakeCollection:
    from app.retrievers.stores import vector as vector_store

    fake = _FakeCollection()
    monkeypatch.setattr(vector_store, "get_vector_store", lambda: fake)
    return fake


def _sources(matches) -> set[str]:
    return {document.metadata["source"] for document, _score in matches}


# --- the store-level guard, which already holds ----------------------------


def test_scoped_search_returns_only_the_callers_documents(collection):
    from app.retrievers.stores.vector import similarity_search

    matches = similarity_search("compensation", k=6, allowed_sources=[ALICE_DOC])

    assert _sources(matches) == {ALICE_DOC}
    assert collection.calls == [{"source": {"$in": [ALICE_DOC]}}]


def test_empty_scope_returns_nothing_without_querying_the_store(collection):
    from app.retrievers.stores.vector import similarity_search

    assert similarity_search("compensation", k=6, allowed_sources=[]) == []
    assert collection.calls == []


def test_missing_scope_raises_rather_than_searching_everything(collection):
    from app.retrievers.stores.vector import similarity_search

    with pytest.raises(ValueError, match="allowed_sources is required"):
        similarity_search("compensation", k=6)
    assert collection.calls == []


# --- P0-1: the request path, fixed 2026-08-30 ------------------------------


def test_hybrid_vector_hop_refuses_to_search_unscoped(collection):
    """`_safe_similarity_search` is the vector hop of hybrid retrieval.

    It used to read `allowed_sources=None` as "search everything" and hand back
    Bob's chunks to whoever asked. It now refuses: a missing scope is a caller
    bug, and raising surfaces it instead of quietly widening the search.
    """
    from app.retrievers.hybrid.retriever import _safe_similarity_search

    with pytest.raises(ValueError, match="allowed_sources is required"):
        # owner=None spelled out: this test is about the source filter, and the
        # hop now refuses to let a caller omit the owner by accident.
        _safe_similarity_search("compensation", k=6, allowed_sources=None, owner=None)
    assert collection.calls == []


def test_a_signature_error_does_not_degrade_into_a_global_search(monkeypatch, collection):
    from app.retrievers.hybrid import retriever

    def _rejects_the_filter(*_args, **kwargs):
        if "allowed_sources" in kwargs:
            raise TypeError("unexpected keyword argument 'allowed_sources'")
        return [(_Document("bob compensation review", {"source": BOB_DOC}), 0.9)]

    monkeypatch.setattr(retriever, "similarity_search", _rejects_the_filter)

    with pytest.raises(TypeError):
        retriever._safe_similarity_search("compensation", k=6, allowed_sources=[ALICE_DOC], owner=None)


# The vector hop the live path actually uses is `app/knowledge/adapters.py`.
# These used to exercise `RAGAgentService._vector_retrieve`, a second, narrower
# copy of the same adapter; when selection moved to the Knowledge Agent that copy
# stopped running, and a test pinned to code nothing calls is how the citation
# bug (`[E1]` reaching the browser) survived a green suite.


def _scope(*sources: str, user: str = "alice") -> AccessScope:
    return AccessScope(
        tenant_id=user,
        user_id=user,
        role="viewer",
        allowed_sources=frozenset(sources),
        allowed_fields=DEFAULT_CONTEXT_FIELDS,
    )


def _plan(top_k: int = 6) -> KnowledgeSourcePlan:
    return KnowledgeSourcePlan(
        source="vector",
        queries=("compensation review",),
        top_k=top_k,
        timeout_ms=5_000,
        required=True,
    )


@pytest.mark.asyncio
async def test_the_vector_adapter_honours_a_resolved_scope(collection):
    """The ordinary path still retrieves, and only the caller's own documents."""
    from app.knowledge.adapters import _retrieve_vector

    items = await _retrieve_vector(_plan(), _scope(ALICE_DOC))

    assert {item.source for item in items} == {ALICE_DOC}


@pytest.mark.asyncio
async def test_the_vector_adapter_returns_nothing_for_a_user_with_no_documents(collection):
    """An empty scope must stay distinct from a missing one: nothing, not everything.

    The orchestrator skips the source before reaching here, so this is the second
    of two independent guards -- the adapter itself must not widen either."""
    from app.knowledge.adapters import _retrieve_vector

    items = await _retrieve_vector(_plan(), _scope(user="carol"))

    assert items == ()
    assert collection.calls == []


@pytest.mark.asyncio
async def test_the_orchestrator_skips_the_vector_source_on_an_empty_scope(collection):
    """The first of the two guards: a source with nothing to search is not run."""
    from app.knowledge.adapters import build_default_adapters
    from app.knowledge.orchestrator import KnowledgeOrchestrator, discard_trace

    strategy = KnowledgeStrategy(sources=(_plan(),), rewrite=False, rationale="test")
    context = await KnowledgeOrchestrator(adapters=build_default_adapters()).retrieve(
        strategy, _scope(user="carol"), discard_trace
    )

    assert context.evidence == ()
    assert context.diagnostics["source_status"]["vector"] == "skipped"
    assert collection.calls == []


# --- P1-4: the store's own owner check -------------------------------------


def _owner(user_id: str) -> Any:
    from app.retrievers.stores.vector import OwnerScope

    return OwnerScope(user_id=user_id, tenant_id=user_id)


def test_a_wrong_source_list_is_still_caught_by_the_owner_metadata(collection):
    """The point of the second clause: source paths are derived, owner is not.

    `allowed_sources` comes from the caller's visible-document computation, so a
    bug there hands the store the wrong paths. `owner_user_id` is written
    independently at ingest, so requiring both narrows what that bug can reach.
    """
    from app.retrievers.stores.vector import similarity_search

    matches = similarity_search(
        "compensation",
        k=6,
        allowed_sources=[ALICE_DOC, BOB_DOC],  # as if the visibility rules leaked one
        owner=_owner("alice"),
    )

    assert _sources(matches) == {ALICE_DOC}


def test_the_shared_corpus_stays_readable(collection):
    """data/docs/ documents have no owner and are not public; they must not be locked out."""
    from app.retrievers.stores.vector import similarity_search

    matches = similarity_search(
        "quarterly",
        k=6,
        allowed_sources=[ALICE_DOC, SHARED_DOC],
        owner=_owner("alice"),
    )

    assert _sources(matches) == {ALICE_DOC, SHARED_DOC}


def test_a_public_document_from_another_owner_stays_readable(collection):
    from app.retrievers.stores.vector import similarity_search

    for row in collection.rows:
        if row["source"] == BOB_DOC:
            row["visibility"] = "public"

    matches = similarity_search(
        "compensation",
        k=6,
        allowed_sources=[BOB_DOC],
        owner=_owner("alice"),
    )

    assert _sources(matches) == {BOB_DOC}


def test_without_an_owner_the_filter_is_source_only(collection):
    """System callers that have no identity keep the previous behaviour."""
    from app.retrievers.stores.vector import similarity_search

    matches = similarity_search("compensation", k=6, allowed_sources=[BOB_DOC])

    assert _sources(matches) == {BOB_DOC}
    assert collection.calls == [{"source": {"$in": [BOB_DOC]}}]


def test_an_owner_scope_needs_an_identity_to_be_built():
    """A scope with no user_id yields no owner clause rather than an empty one."""
    from app.domain.knowledge import AccessScope
    from app.retrievers.stores.vector import OwnerScope

    assert OwnerScope.from_access_scope(object()) is None
    scope = AccessScope(tenant_id="t", user_id="alice", role="viewer")
    assert OwnerScope.from_access_scope(scope) == OwnerScope(user_id="alice", tenant_id="t")


def test_a_chunk_the_store_returns_outside_the_filter_is_dropped(collection, monkeypatch):
    """Post-condition against the filter not doing what we asked.

    Chroma applies the `$in` itself; this only fires on a malformed clause or a
    very large `$in` behaving unexpectedly.
    """
    from app.retrievers.stores import vector as vector_store

    monkeypatch.setattr(
        vector_store,
        "get_vector_store",
        lambda: type(
            "Leaky",
            (),
            {
                "similarity_search_with_relevance_scores": staticmethod(
                    lambda query, k=4, filter=None: [
                        (_Document("bob compensation review", {"source": BOB_DOC}), 0.9),
                        (_Document("alice quarterly notes", {"source": ALICE_DOC}), 0.8),
                    ]
                )
            },
        )(),
    )

    matches = vector_store.similarity_search("compensation", k=6, allowed_sources=[ALICE_DOC])

    assert _sources(matches) == {ALICE_DOC}


def test_a_chunk_with_no_owner_metadata_is_excluded(collection):
    """Deployment hazard, pinned so it is not discovered in production.

    Verified against chromadb 1.5.9: `$eq` does not match an absent key, so a
    chunk indexed before ingest started writing owner metadata becomes invisible
    once the owner clause is on. Reindexing writes the metadata
    (app/services/documents/ingest.py::_canonical_metadata), so any store with
    pre-existing chunks must be reindexed before this ships.
    """
    from app.retrievers.stores.vector import similarity_search

    legacy = {
        "source": "/uploads/alice/legacy.pdf",
        "document_id": "doc-legacy",
        "text": "alice legacy quarterly notes",
        # No owner_user_id / tenant_id / visibility at all -- the pre-2026-08 shape.
    }
    collection.rows.append(legacy)

    unscoped = similarity_search("quarterly", k=6, allowed_sources=[legacy["source"]])
    scoped = similarity_search("quarterly", k=6, allowed_sources=[legacy["source"]], owner=_owner("alice"))

    assert _sources(unscoped) == {legacy["source"]}, "source-only filtering still finds it"
    assert scoped == [], "the owner clause drops it -- reindex before deploying"
