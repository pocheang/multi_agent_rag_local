"""Central tenant, RBAC, document, ACL, and field authorization resolver."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.core.config import Settings, get_settings
from app.domain.knowledge import AccessScope
from app.services.documents.index_manager import list_indexed_files
from app.services.runtime.rag_runtime_scope import is_under_path
from app.services.security.rbac import can

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


def list_visible_document_rows(
    actor: Mapping[str, Any],
    *,
    indexed_rows: Sequence[Mapping[str, Any]] | None = None,
    settings: Settings | None = None,
) -> list[dict[str, Any]]:
    """Return document rows visible under tenant, role, owner, and visibility rules."""

    active_settings = settings or get_settings()
    rows = indexed_rows if indexed_rows is not None else list_indexed_files()
    user_id = str(actor.get("user_id", "") or "").strip()
    tenant_id = str(actor.get("tenant_id", "") or user_id).strip()
    role = str(actor.get("role", "viewer") or "viewer").strip().lower()
    permissions = frozenset(str(value) for value in actor.get("permissions", ()) or ())
    acl_tags = frozenset(str(value) for value in actor.get("acl_tags", ()) or ())
    cross_tenant = role == "admin" and ("*" in permissions or "tenant:cross_read" in permissions)
    docs_root = active_settings.docs_path.resolve()
    user_upload_root = (active_settings.uploads_path / user_id).resolve() if user_id else None
    visible: list[dict[str, Any]] = []

    for raw_row in rows:
        row = dict(raw_row)
        source = str(row.get("source", "") or "").strip()
        if not source:
            continue
        try:
            source_path = Path(source).resolve()
        except (OSError, RuntimeError, ValueError):
            continue

        row_tenant = str(row.get("tenant_id", "") or "").strip()
        if row_tenant and row_tenant != tenant_id and not cross_tenant:
            continue

        row_acl = frozenset(str(value) for value in row.get("acl_tags", ()) or ())
        if row_acl and not row_acl.intersection(acl_tags) and not cross_tenant:
            continue

        owner_user_id = str(row.get("owner_user_id", "") or "").strip()
        visibility = str(row.get("visibility", "private") or "private").strip().lower()
        shared_document = is_under_path(source_path, docs_root)
        owned_document = owner_user_id == user_id or (
            not owner_user_id and user_upload_root is not None and user_upload_root in source_path.parents
        )
        admin_document = role == "admin" and (cross_tenant or bool(row_tenant and row_tenant == tenant_id))
        if shared_document or visibility == "public" or owned_document or admin_document:
            visible.append(row)
    return visible


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
        actor_dict = {
            "tenant_id": tenant_id,
            "user_id": user_id,
            "role": role,
            "permissions": actor.permissions,
            "acl_tags": requested_scope.acl_tags or frozenset(),
        }
        if not can("document:read", actor_dict) and "document:read" not in actor.permissions:
            raise AccessScopeError("document read permission is required")

        visible_rows = [dict(row) for row in self._document_provider(actor_dict)]
        requested_acl = requested_scope.acl_tags or frozenset()
        scoped_rows = []
        for row in visible_rows:
            row_acl = frozenset(str(value) for value in row.get("acl_tags", ()) or ())
            if row_acl and not row_acl.intersection(requested_acl) and role != "admin":
                continue
            scoped_rows.append(row)

        visible_sources = frozenset(
            str(row.get("source", "") or "").strip() for row in scoped_rows if str(row.get("source", "") or "").strip()
        )
        visible_document_ids = frozenset(
            str(row.get("document_id", "") or "").strip()
            for row in scoped_rows
            if str(row.get("document_id", "") or "").strip()
        )
        allowed_sources = self._intersect_requested(
            requested_scope.allowed_sources,
            visible_sources,
            label="source",
        )
        document_ids = self._intersect_requested(
            requested_scope.document_ids,
            visible_document_ids,
            label="document",
        )
        requested_fields = requested_scope.allowed_fields
        allowed_fields = (
            DEFAULT_CONTEXT_FIELDS
            if requested_fields is None
            else frozenset(requested_fields).intersection(DEFAULT_CONTEXT_FIELDS)
        )
        if not allowed_fields:
            raise AccessScopeError("requested scope contains no authorized context fields")
        return AccessScope(
            tenant_id=tenant_id,
            user_id=user_id,
            role=role,
            permissions=actor.permissions,
            document_ids=document_ids,
            allowed_sources=allowed_sources,
            acl_tags=frozenset(requested_acl),
            allowed_fields=allowed_fields,
        )

    @staticmethod
    def _intersect_requested(
        requested: frozenset[str] | None,
        visible: frozenset[str],
        *,
        label: str,
    ) -> frozenset[str]:
        if requested is None:
            return visible
        normalized = frozenset(str(value).strip() for value in requested if str(value).strip())
        unauthorized = normalized.difference(visible)
        if unauthorized:
            raise AccessScopeError(f"requested {label} scope contains {len(unauthorized)} unauthorized value(s)")
        return normalized


__all__ = [
    "AccessScopeError",
    "AccessScopeResolver",
    "DEFAULT_CONTEXT_FIELDS",
    "list_visible_document_rows",
]
