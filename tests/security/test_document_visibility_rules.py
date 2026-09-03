"""Which documents an actor can see, stated one rule at a time.

`list_visible_document_rows` decides what every later stage is allowed to know
about: the access scope is built from its output, and `similarity_search` is
scoped by the source list it produces. Fifteen test files reference this module,
and every one of them replaces this function with a stub -- so the rules
themselves, tenant, ACL, ownership, visibility and the admin exception, ran
untested.

Pinned before the function was split up, but worth having either way: the
interesting cases here are the ones where a row is *not* visible, and a
refactor is not the only thing that can quietly turn one of those around.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.security.access_scope import list_visible_document_rows


class _Settings:
    def __init__(self, docs_path: Path, uploads_path: Path) -> None:
        self.docs_path = docs_path
        self.uploads_path = uploads_path


# Nothing here is created on disk: the rules resolve and compare paths, they
# never open one. That also sidesteps pytest's tmp_path, whose basetemp needs
# directory permissions not available on every Windows checkout -- see the note
# in tests/mcp/test_approval_resume.py.
_ROOT = (Path(__file__).resolve().parent / "_visibility_fixture").resolve()


@pytest.fixture
def roots() -> _Settings:
    return _Settings(_ROOT / "docs", _ROOT / "uploads")


def _actor(**overrides):
    actor = {"user_id": "alice", "tenant_id": "acme", "role": "viewer", "permissions": (), "acl_tags": ()}
    actor.update(overrides)
    return actor


def _row(source: Path | str, **overrides):
    row = {"source": str(source), "document_id": "doc-1", "tenant_id": "acme"}
    row.update(overrides)
    return row


def _visible(actor, rows, settings) -> list[str]:
    return [row["source"] for row in list_visible_document_rows(actor, indexed_rows=rows, settings=settings)]


def test_a_row_without_a_source_is_dropped(roots: _Settings) -> None:
    rows = [_row(""), _row("   ")]

    assert _visible(_actor(), rows, roots) == []


def test_a_shared_document_is_visible_to_everyone_in_the_tenant(roots: _Settings) -> None:
    shared = roots.docs_path / "handbook.pdf"

    assert _visible(_actor(), [_row(shared)], roots) == [str(shared)]


def test_another_users_private_upload_is_not_visible(roots: _Settings) -> None:
    """The property everything else in tests/security/ exists to protect."""

    theirs = roots.uploads_path / "bob" / "salaries.pdf"

    assert _visible(_actor(), [_row(theirs, owner_user_id="bob")], roots) == []


def test_a_document_is_visible_to_the_user_who_owns_it(roots: _Settings) -> None:
    mine = roots.uploads_path / "alice" / "notes.pdf"

    assert _visible(_actor(), [_row(mine, owner_user_id="alice")], roots) == [str(mine)]


def test_an_unowned_document_under_the_users_upload_root_counts_as_theirs(roots: _Settings) -> None:
    """Ownership metadata arrived later than the upload layout; the path still says whose it is."""

    mine = roots.uploads_path / "alice" / "legacy.pdf"

    assert _visible(_actor(), [_row(mine, owner_user_id="")], roots) == [str(mine)]


def test_a_public_document_is_visible_wherever_it_lives(roots: _Settings) -> None:
    theirs = roots.uploads_path / "bob" / "announcement.pdf"

    assert _visible(_actor(), [_row(theirs, owner_user_id="bob", visibility="public")], roots) == [str(theirs)]


def test_another_tenants_row_is_dropped_even_when_it_is_public(roots: _Settings) -> None:
    """Tenant is checked before visibility, so public does not cross the boundary."""

    other = roots.docs_path / "their-handbook.pdf"
    rows = [_row(other, tenant_id="globex", visibility="public")]

    assert _visible(_actor(), rows, roots) == []


@pytest.mark.parametrize("permission", ["*", "tenant:cross_read"])
def test_an_admin_holding_a_cross_tenant_permission_sees_across_the_boundary(roots: _Settings, permission: str) -> None:
    other = roots.docs_path / "their-handbook.pdf"
    actor = _actor(role="admin", permissions=(permission,))

    assert _visible(actor, [_row(other, tenant_id="globex")], roots) == [str(other)]


def test_an_admin_without_that_permission_stays_inside_the_tenant(roots: _Settings) -> None:
    other = roots.docs_path / "their-handbook.pdf"
    actor = _actor(role="admin", permissions=("admin:user_manage",))

    assert _visible(actor, [_row(other, tenant_id="globex")], roots) == []


def test_an_admin_sees_a_private_document_of_their_own_tenant(roots: _Settings) -> None:
    theirs = roots.uploads_path / "bob" / "salaries.pdf"
    actor = _actor(role="admin", permissions=("admin:user_manage",))

    assert _visible(actor, [_row(theirs, owner_user_id="bob")], roots) == [str(theirs)]


def test_a_tagged_row_needs_a_matching_tag(roots: _Settings) -> None:
    tagged = roots.docs_path / "restricted.pdf"
    rows = [_row(tagged, acl_tags=("legal",))]

    assert _visible(_actor(), rows, roots) == []
    assert _visible(_actor(acl_tags=("legal",)), rows, roots) == [str(tagged)]
    assert _visible(_actor(acl_tags=("finance",)), rows, roots) == []


def test_an_untagged_row_is_not_restricted_by_the_actors_tags(roots: _Settings) -> None:
    plain = roots.docs_path / "handbook.pdf"

    assert _visible(_actor(acl_tags=("legal",)), [_row(plain)], roots) == [str(plain)]


def test_a_cross_tenant_admin_bypasses_the_tag_check_too(roots: _Settings) -> None:
    tagged = roots.docs_path / "restricted.pdf"
    actor = _actor(role="admin", permissions=("*",))

    assert _visible(actor, [_row(tagged, acl_tags=("legal",))], roots) == [str(tagged)]


def test_an_actor_with_no_tenant_falls_back_to_their_own_id(roots: _Settings) -> None:
    """A single-tenant deployment has no tenant column; the user is the tenant."""

    mine = roots.docs_path / "handbook.pdf"
    actor = _actor(tenant_id="", user_id="alice")

    assert _visible(actor, [_row(mine, tenant_id="alice")], roots) == [str(mine)]
    assert _visible(actor, [_row(mine, tenant_id="acme")], roots) == []
