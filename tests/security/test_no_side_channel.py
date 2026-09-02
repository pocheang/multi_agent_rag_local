"""Diagnostics must not count what the caller was not allowed to see.

Because retrieval runs unscoped and the scope filter is applied afterwards
(P0-1), `ContextBuilder` knows exactly how many of another tenant's chunks it
just discarded -- and publishes the number:

    "context_input_count": len(raw),
    "context_scope_dropped": len(raw) - len(authorized),

These flow into `EvidenceBundle.diagnostics` and out through the response's
`execution_metadata`, so a user who asks about a topic they have no documents on
can read how many documents *other* users have on it. That is threat T2 in
docs/superpowers/plans/2026-08-29-user-data-isolation.md.

Nothing in app/ or frontend/ reads these two keys, so the fix is to log them
instead of returning them. Fixing P0-1 removes the signal at the source; this
test pins the property either way.
"""

from __future__ import annotations

from app.domain.contracts import EvidenceItem
from app.domain.knowledge import AccessScope
from app.knowledge.context import ContextBuilder
from app.services.security.access_scope import DEFAULT_CONTEXT_FIELDS

ALICE_DOC = "/uploads/alice/notes.pdf"
BOB_DOC = "/uploads/bob/salary.pdf"

# Keys that quantify what the scope filter removed. Adding one here is a
# deliberate decision to expose it to the caller.
LEAKY_COUNT_KEYS = ("context_scope_dropped", "context_input_count")


def _scope() -> AccessScope:
    return AccessScope(
        tenant_id="alice",
        user_id="alice",
        role="viewer",
        allowed_sources=frozenset({ALICE_DOC}),
        allowed_fields=DEFAULT_CONTEXT_FIELDS,
    )


def _mixed_evidence() -> tuple[EvidenceItem, ...]:
    mine = EvidenceItem(
        content="alice quarterly notes",
        source=ALICE_DOC,
        document_id="doc-alice",
        retriever="vector",
    )
    theirs = tuple(
        EvidenceItem(
            content=f"bob compensation review {index}",
            source=BOB_DOC,
            document_id="doc-bob",
            chunk_id=f"chunk-bob-{index}",
            retriever="vector",
        )
        for index in range(4)
    )
    return (mine, *theirs)


def test_only_authorized_evidence_reaches_the_context():
    bundle = ContextBuilder(token_budget=4000).build(_mixed_evidence(), _scope())

    assert {item.source for item in bundle.evidence} == {ALICE_DOC}
    assert BOB_DOC not in bundle.rendered_context


def test_diagnostics_do_not_reveal_how_much_was_dropped():
    bundle = ContextBuilder(token_budget=4000).build(_mixed_evidence(), _scope())

    exposed = [key for key in LEAKY_COUNT_KEYS if key in bundle.diagnostics]
    assert not exposed, (
        f"{exposed} tells the caller how many documents they were denied. Log these instead of returning them."
    )


def test_the_authorized_count_may_still_be_reported():
    """What the caller *did* get is theirs to know; guards against overcorrecting."""
    bundle = ContextBuilder(token_budget=4000).build(_mixed_evidence(), _scope())

    assert bundle.diagnostics["context_output_count"] == 1
