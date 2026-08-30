"""The authorization primitives must deny by default, on every evidence layer.

`evidence_is_authorized` is the last line of defence before evidence reaches a
model. Since phase 1 retrieval is scoped too, so this is no longer the *only*
thing standing between users -- which is exactly why it needs pinning: a defence
that never visibly fires is the one a refactor quietly removes.

Two properties matter and neither is obvious from reading the call sites:

1. An empty scope denies everything (fail-closed). A future refactor that makes
   an empty AccessScope mean "unrestricted" would silently open every document
   to every user.
2. Every layer that can carry user content is subject to the scope. `web` and
   `tool` are legitimately exempt -- they are not user documents and carry no
   owner. `memory` is not exempt: its store is per tenant and user
   (app/memory/long_term.py:54) and its URIs name that namespace, so it is
   checked against the namespace rather than against allowed_sources, which
   only ever holds document paths. See P0-2 in
   docs/superpowers/plans/2026-08-29-user-data-isolation.md.
"""

from __future__ import annotations

from app.domain.contracts import EvidenceItem
from app.domain.knowledge import AccessScope
from app.privacy.dlp import evidence_is_authorized, mask_evidence
from app.services.security.access_scope import DEFAULT_CONTEXT_FIELDS

ALICE_DOC = "/uploads/alice/private.pdf"
BOB_DOC = "/uploads/bob/salary.pdf"


def _item(**overrides) -> EvidenceItem:
    payload = {
        "content": "quarterly compensation review",
        "source": BOB_DOC,
        "document_id": "doc-bob-1",
        "retriever": "vector",
    }
    payload.update(overrides)
    return EvidenceItem(**payload)


def _scope(**overrides) -> AccessScope:
    payload = {
        "tenant_id": "alice",
        "user_id": "alice",
        "role": "viewer",
        "allowed_sources": frozenset({ALICE_DOC}),
        "allowed_fields": DEFAULT_CONTEXT_FIELDS,
    }
    payload.update(overrides)
    return AccessScope(**payload)


# --- fail-closed properties that hold today; these are regression guards -----


def test_empty_scope_denies_every_document_item():
    empty = _scope(allowed_sources=frozenset(), document_ids=frozenset())
    assert evidence_is_authorized(_item(), empty) is False
    assert evidence_is_authorized(_item(source=ALICE_DOC, document_id="doc-alice-1"), empty) is False


def test_item_outside_allowed_sources_is_denied():
    assert evidence_is_authorized(_item(), _scope()) is False


def test_item_inside_allowed_sources_is_allowed():
    """Guards against 'fixing' isolation by denying everything."""
    mine = _item(source=ALICE_DOC, document_id="doc-alice-1")
    assert evidence_is_authorized(mine, _scope()) is True


def test_document_id_restriction_is_enforced_independently():
    scope = _scope(allowed_sources=frozenset({ALICE_DOC}), document_ids=frozenset({"doc-alice-1"}))
    mismatched = _item(source=ALICE_DOC, document_id="doc-bob-1")
    assert evidence_is_authorized(mismatched, scope) is False


def test_acl_tag_mismatch_is_denied():
    scope = _scope(acl_tags=frozenset({"finance"}))
    tagged = _item(source=ALICE_DOC, document_id="doc-alice-1", acl_tags=frozenset({"legal"}))
    assert evidence_is_authorized(tagged, scope) is False


def test_mask_evidence_drops_an_unauthorized_item_entirely():
    assert mask_evidence(_item(), _scope()) is None


def test_mask_evidence_redacts_content_when_the_field_is_not_granted():
    scope = _scope(allowed_fields=DEFAULT_CONTEXT_FIELDS - {"content"})
    masked = mask_evidence(_item(source=ALICE_DOC, document_id="doc-alice-1"), scope)
    assert masked is not None
    assert masked.content == "[REDACTED_FIELD]"


# --- P0-2: the memory layer is checked by namespace, not exempted ---------


def test_memory_from_another_owners_namespace_is_denied():
    """`web` and `tool` are exempt by design; `memory` carries an owner.

    A memory URI names its tenant and user (app/knowledge/adapters.py:186), so
    the layer is checked against that namespace rather than against
    allowed_sources, which only ever holds document paths.
    """
    theirs = _item(layer="memory", retriever="gbrain", source="memory://bob/bob/mem-1")
    assert evidence_is_authorized(theirs, _scope()) is False


def test_memory_carrying_a_document_path_is_denied():
    """A memory item must declare a memory:// namespace to be authorized at all."""
    forged = _item(layer="memory", retriever="gbrain")
    assert evidence_is_authorized(forged, _scope()) is False


def test_a_users_own_memory_is_authorized():
    """Guards the namespace check against dropping every memory item."""
    mine = _item(layer="memory", retriever="gbrain", source="memory://alice/alice/mem-1")
    assert evidence_is_authorized(mine, _scope()) is True


def test_a_prefix_collision_does_not_grant_access():
    """`memory://alice/alice2/` must not match the `memory://alice/alice/` prefix."""
    lookalike = _item(layer="memory", retriever="gbrain", source="memory://alice/alice2/mem-1")
    assert evidence_is_authorized(lookalike, _scope()) is False


def test_web_and_tool_layers_stay_exempt():
    """Documents the deliberate exemption so the P0-2 fix does not overreach."""
    for layer in ("web", "tool"):
        item = _item(layer=layer, source="https://example.com/a", document_id="web-1", retriever=layer)
        assert evidence_is_authorized(item, _scope()) is True
