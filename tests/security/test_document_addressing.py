"""Managing a document must not reach outside the caller's own uploads.

`DELETE /documents/{filename}` and `POST /documents/{filename}/reindex` accept an
optional `source` *query parameter*, and when it is present the visibility-based
resolution is skipped entirely (app/api/routes/public/documents.py:110,155):

    source = normalize_string(source) or _resolve_manageable_source_for_filename(filename, user)

The only remaining check is `_is_source_manageable_for_user`, which for an admin
returns True for anything under the shared uploads root -- so an admin can name
another user's file directly and delete it, with no `tenant:cross_read` check and
with an audit record that names only the filename, not the owner. See P0-3 in
docs/superpowers/plans/2026-08-29-user-data-isolation.md.
"""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

import pytest

from app.api.deps import documents as documents_deps

ALICE = {"user_id": "alice", "username": "alice", "role": "viewer", "permissions": []}
BOB = {"user_id": "bob", "username": "bob", "role": "viewer", "permissions": []}
# The shape the auth layer actually produces: no `permissions` key at all
# (app/services/auth/session_manager.py:66 returns user_id/username/role/status/
# credit_balance). Nothing grants cross-tenant rights today, so this is what
# every real admin looks like.
ADMIN = {"user_id": "root", "username": "root", "role": "admin"}
# A hypothetical admin that some future flow has granted cross-tenant rights.
CROSS_TENANT_ADMIN = {"user_id": "root", "username": "root", "role": "admin", "permissions": ["*"]}


@pytest.fixture
def uploads(monkeypatch) -> Path:
    # Not tmp_path: its basetemp root needs directory permissions that are not
    # available on every Windows checkout (see tests/api/test_advanced_rag_roundtrip.py).
    root = Path(tempfile.mkdtemp(prefix="querymind-uploads-"))
    for owner in ("alice", "bob"):
        (root / "uploads" / owner).mkdir(parents=True, exist_ok=True)
        (root / "uploads" / owner / "report.pdf").write_bytes(b"%PDF-1.4\n")

    class _Settings:
        uploads_path = root / "uploads"
        docs_path = root / "docs"

    _Settings.docs_path.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(documents_deps, "settings", _Settings)
    try:
        yield root / "uploads"
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _rows(uploads: Path) -> list[dict]:
    return [
        {
            "filename": "report.pdf",
            "source": str(uploads / owner / "report.pdf"),
            "document_id": f"doc-{owner}",
            "owner_user_id": owner,
            "tenant_id": owner,
            "visibility": "private",
            "chunks": 3,
            "agent_class": "general",
        }
        for owner in ("alice", "bob")
    ]


# --- what already holds ----------------------------------------------------


def test_a_user_can_manage_their_own_upload(uploads):
    assert documents_deps._is_source_manageable_for_user(str(uploads / "alice" / "report.pdf"), ALICE) is True


def test_a_user_cannot_manage_another_users_identically_named_upload(uploads):
    assert documents_deps._is_source_manageable_for_user(str(uploads / "bob" / "report.pdf"), ALICE) is False


def test_a_traversal_path_does_not_escape_the_owners_directory(uploads):
    escaped = str(uploads / "alice" / ".." / "bob" / "report.pdf")
    assert documents_deps._is_source_manageable_for_user(escaped, ALICE) is False


def test_an_ambiguous_filename_resolves_to_nothing(uploads, monkeypatch):
    """Two owners, one filename: resolution must refuse rather than guess.

    `_resolve_manageable_source_for_filename` returns None unless exactly one
    candidate matches, which is what makes the *filename-only* form of the
    endpoint safe. It is the `source` query parameter that bypasses this.
    """
    from app.api.routes.public import documents as documents_route

    monkeypatch.setattr(documents_deps, "list_visible_document_rows", lambda user, settings=None: _rows(uploads))
    monkeypatch.setattr(documents_route, "_list_visible_documents_for_user", lambda user: _rows(uploads))

    # CROSS_TENANT_ADMIN so both rows are genuinely manageable and the ambiguity
    # itself is what refuses, rather than the narrower reach doing it first.
    assert documents_route._resolve_manageable_source_for_filename("report.pdf", CROSS_TENANT_ADMIN) is None


# --- P0-3: the admin escape hatch -----------------------------------------


def test_an_admin_cannot_manage_an_arbitrary_users_upload_without_cross_tenant_rights(uploads):
    """Admin reach is gated on `tenant:cross_read`, not on the role alone.

    The permission already existed and was honoured by
    app/services/security/access_scope.py:50 for *reading*; this helper did not
    consult it, so `?source=/uploads/bob/report.pdf` was enough to act on Bob's
    file -- while the same admin could not list it.
    """
    assert documents_deps._is_source_manageable_for_user(str(uploads / "bob" / "report.pdf"), ADMIN) is False


def test_a_cross_tenant_admin_may_still_manage_another_users_upload(uploads):
    """The gate is a gate, not a wall: an explicit grant still works."""
    assert (
        documents_deps._is_source_manageable_for_user(str(uploads / "bob" / "report.pdf"), CROSS_TENANT_ADMIN) is True
    )


def test_an_admin_still_manages_their_own_uploads(uploads):
    """Narrowing the reach must not lock an admin out of their own documents."""
    (uploads / "root").mkdir(parents=True, exist_ok=True)
    (uploads / "root" / "report.pdf").write_bytes(b"%PDF-1.4\n")

    assert documents_deps._is_source_manageable_for_user(str(uploads / "root" / "report.pdf"), ADMIN) is True


def test_a_source_outside_the_uploads_root_is_never_manageable(uploads):
    """Applies to admins too -- nothing outside uploads/ is a managed document."""
    for user in (ALICE, ADMIN):
        assert documents_deps._is_source_manageable_for_user("/etc/passwd", user) is False
