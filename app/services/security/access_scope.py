"""Central tenant, RBAC, document, ACL, and field authorization resolver."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.core.config import Settings, get_settings
from app.domain.knowledge import AccessScope
from app.services.documents.index_manager import list_indexed_files
from app.services.runtime.rag_runtime_scope import is_under_path
from app.services.security.rbac import Permission, can

if TYPE_CHECKING:
    from app.orchestration.request import RequestActor, RequestScope

DEFAULT_CONTEXT_FIELDS = frozenset(
    {
        "content",
        "source",
        "document_id",
        "version",
        "page",
        "chunk_id",
        "image_id",
        "artifact_uri",
    }
)


class AccessScopeError(PermissionError):
    """Raised when a request cannot be reduced to an authorized scope."""


@dataclass(frozen=True)
class _Viewer:
    """The actor reduced to what the visibility rules actually consult."""

    user_id: str
    tenant_id: str
    role: str
    acl_tags: frozenset[str]
    cross_tenant: bool
    docs_root: Path
    upload_root: Path | None


def _viewer_from(actor: Mapping[str, Any], settings: Settings) -> _Viewer:
    user_id = str(actor.get("user_id", "") or "").strip()
    permissions = frozenset(str(value) for value in actor.get("permissions", ()) or ())
    role = str(actor.get("role", "viewer") or "viewer").strip().lower()
    return _Viewer(
        user_id=user_id,
        # A single-tenant deployment has no tenant column, so the user is the tenant.
        tenant_id=str(actor.get("tenant_id", "") or user_id).strip(),
        role=role,
        acl_tags=frozenset(str(value) for value in actor.get("acl_tags", ()) or ()),
        cross_tenant=role == "admin" and ("*" in permissions or "tenant:cross_read" in permissions),
        docs_root=settings.docs_path.resolve(),
        upload_root=(settings.uploads_path / user_id).resolve() if user_id else None,
    )


def list_visible_document_rows(
    actor: Mapping[str, Any],
    *,
    indexed_rows: Sequence[Mapping[str, Any]] | None = None,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Return document rows visible under tenant, role, owner, and visibility rules."""

    active_settings = settings or get_settings()
    rows = indexed_rows if indexed_rows is not None else list_indexed_files()
    viewer = _viewer_from(actor, active_settings)

    visible: list[dict[str, Any]] = []
    for raw_row in rows:
        row = dict(raw_row)
        source_path = _resolved_source(row)
        if source_path is None:
            continue
        if not _within_reach(row, viewer):
            continue
        if _is_visible_to(row, source_path, viewer):
            visible.append(row)
    return visible


def _resolved_source(row: Mapping[str, Any]) -> Path | None:
    """A row this system cannot name a path for is not a row it can authorize."""

    source = str(row.get("source", "") or "").strip()
    if not source:
        return None
    try:
        return Path(source).resolve()
    except (OSError, RuntimeError, ValueError):
        return None


def _within_reach(row: Mapping[str, Any], viewer: _Viewer) -> bool:
    """Tenant and ACL: the two boundaries checked before any grant is considered.

    Order matters. These run ahead of the four grants below, so a public
    document still does not cross a tenant boundary. A cross-tenant admin is
    exempt from both -- that permission is what it means.
    """

    if viewer.cross_tenant:
        return True
    row_tenant = str(row.get("tenant_id", "") or "").strip()
    if row_tenant and row_tenant != viewer.tenant_id:
        return False
    row_acl = frozenset(str(value) for value in row.get("acl_tags", ()) or ())
    return not row_acl or bool(row_acl.intersection(viewer.acl_tags))


def _is_visible_to(row: Mapping[str, Any], source_path: Path, viewer: _Viewer) -> bool:
    """Four independent grants; any one of them is enough."""

    if is_under_path(source_path, viewer.docs_root):
        return True
    if str(row.get("visibility", "private") or "private").strip().lower() == "public":
        return True
    return _is_owned_by(row, source_path, viewer) or _is_admin_of(row, viewer)


def _is_owned_by(row: Mapping[str, Any], source_path: Path, viewer: _Viewer) -> bool:
    """Owner metadata first, and the upload layout for rows indexed before it existed."""

    owner_user_id = str(row.get("owner_user_id", "") or "").strip()
    return owner_user_id == viewer.user_id or (
        not owner_user_id and viewer.upload_root is not None and viewer.upload_root in source_path.parents
    )


def _is_admin_of(row: Mapping[str, Any], viewer: _Viewer) -> bool:
    row_tenant = str(row.get("tenant_id", "") or "").strip()
    return viewer.role == "admin" and (viewer.cross_tenant or bool(row_tenant and row_tenant == viewer.tenant_id))


class AccessScopeResolver:
    """Resolve requested filters to a fail-closed immutable AccessScope."""

    def __init__(
        self,
        document_provider: Callable[[Mapping[str, Any]], Sequence[Mapping[str, Any]]] | None = None,
    ) -> None:
        self._document_provider = document_provider or list_visible_document_rows

    def resolve(self, actor: RequestActor | None, requested_scope: RequestScope) -> AccessScope:
        if actor is None or not (actor.user_id or "").strip():
            raise AccessScopeError("authenticated user identity is required")
        user_id = str(actor.user_id).strip()
        tenant_id = str(actor.tenant_id or user_id).strip()
        role = str(actor.role or "viewer").strip().lower()
        requested_acl = requested_scope.acl_tags or frozenset()
        actor_dict = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "role": role,
            "permissions": actor.permissions,
            "acl_tags": requested_acl,
        }
        if not can(Permission.DOCUMENT_READ, actor_dict) and Permission.DOCUMENT_READ not in actor.permissions:
            raise AccessScopeError("document read permission is required")

        scoped_rows = _rows_matching_requested_acl(self._document_provider(actor_dict), requested_acl, role)
        allowed_sources = self._intersect_requested(
            _field_values(scoped_rows, "source"),
            requested_scope.allowed_sources,
            label="source",
        )
        document_ids = self._intersect_requested(
            _field_values(scoped_rows, "document_id"),
            requested_scope.document_ids,
            label="document",
        )
        return AccessScope(
            tenant_id=tenant_id,
            user_id=user_id,
            role=role,
            permissions=actor.permissions,
            document_ids=document_ids,
            allowed_sources=allowed_sources,
            acl_tags=frozenset(requested_acl),
            allowed_fields=_allowed_fields(requested_scope.allowed_fields),
        )

    @staticmethod
    def _intersect_requested(
        visible: frozenset[str],
        requested: frozenset[str] | None,
        *,
        label: str,
    ) -> frozenset[str]:
        """No request means everything visible; a request may only narrow it.

        Asking for something outside the visible set is refused rather than
        silently dropped -- a caller that names another tenant's document should
        hear about it, and the count alone is what it hears.
        """

        if requested is None:
            return visible
        normalized = frozenset(str(value).strip() for value in requested if str(value).strip())
        unauthorized = normalized.difference(visible)
        if unauthorized:
            raise AccessScopeError(f"requested {label} scope contains {len(unauthorized)} unauthorized value(s)")
        return normalized


def _rows_matching_requested_acl(
    rows: Sequence[Mapping[str, Any]], requested_acl: frozenset[str], role: str
) -> list[dict[str, Any]]:
    """Narrow the visible rows to the tags this request asked to work under."""

    scoped: list[dict[str, Any]] = []
    for raw_row in rows:
        row = dict(raw_row)
        row_acl = frozenset(str(value) for value in row.get("acl_tags", ()) or ())
        if row_acl and not row_acl.intersection(requested_acl) and role != "admin":
            continue
        scoped.append(row)
    return scoped


def _field_values(rows: Sequence[Mapping[str, Any]], field: str) -> frozenset[str]:
    return frozenset(value for row in rows if (value := str(row.get(field, "") or "").strip()))


def _allowed_fields(requested_fields: frozenset[str] | None) -> frozenset[str]:
    """Context fields are an allowlist: a request may narrow it and never extend it."""

    allowed = (
        DEFAULT_CONTEXT_FIELDS
        if requested_fields is None
        else frozenset(requested_fields).intersection(DEFAULT_CONTEXT_FIELDS)
    )
    if not allowed:
        raise AccessScopeError("requested scope contains no authorized context fields")
    return allowed


__all__ = [
    "AccessScopeError",
    "AccessScopeResolver",
    "DEFAULT_CONTEXT_FIELDS",
    "list_visible_document_rows",
]
