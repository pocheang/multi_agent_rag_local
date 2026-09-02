"""Read and change the running configuration from the console.

Before this, an administrator could reload configuration but not write it: the
reload endpoint re-read a file no HTTP path could produce, so from a browser it
did nothing unless somebody had already edited the file on the host. These two
endpoints close that half of the loop.

The write goes to the configuration centre, never to the rendered runtime file.
The centre owns version history and rollback; writing the file instead would mean
reimplementing both, badly, and would leave two writers for one document.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.application.config_reload import ConfigWriteRefused, write_config_values
from app.api.dependencies import _audit, _require_permission, _require_user
from app.api.transport.errors import bad_request
from app.core.config import get_settings
from app.core.config_schema import describe
from app.core.remote_config import RemoteDocuments, remote_config_enabled
from app.services.security.rbac import Permission

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin", "config"])


class ConfigValues(BaseModel):
    """A partial change: only the fields the administrator actually edited."""

    values: dict[str, str] = Field(default_factory=dict)
    data_id: str | None = None


@router.get("/admin/config/schema")
def admin_config_schema(request: Request, user: dict[str, Any] = Depends(_require_user)):
    """Every editable field, its current value, and which layer supplied it."""

    _require_permission(user, Permission.ADMIN_OPS_MANAGE, request, "admin")
    documents = RemoteDocuments() if remote_config_enabled() else None
    return {
        "config_centre_enabled": remote_config_enabled(),
        "fields": describe(get_settings(), documents),
    }


@router.post("/admin/config/values")
def admin_save_config(payload: ConfigValues, request: Request, user: dict[str, Any] = Depends(_require_user)):
    """Write edited values to the configuration centre and reload.

    Each edited key is written back to the document that already defines it, and
    each such document is rewritten whole from what this process currently reads
    plus the edit -- so a key the administrator did not touch keeps its value.
    Reading and writing through the same `RemoteDocuments` is what makes that
    safe: the page showed what this read returns.

    A value pinned in the process environment is rejected rather than written.
    Writing it would appear to succeed and change nothing, because the
    environment outranks the centre -- and a console that lies about what it
    changed is worse than one that refuses.
    """

    _require_permission(user, Permission.ADMIN_OPS_MANAGE, request, "admin")
    if not payload.values:
        raise bad_request("no values to save")

    try:
        written = write_config_values(payload.values, payload.data_id)
    except ConfigWriteRefused as exc:
        _audit(
            request,
            action="admin.config.save",
            resource_type="admin",
            result="failure",
            user=user,
            detail=f"refused: {'; '.join(sorted(payload.values))}",
        )
        raise bad_request(str(exc)) from exc

    _audit(
        request,
        action="admin.config.save",
        resource_type="admin",
        result="success",
        resource_id=",".join(written),
        user=user,
        detail=f"changed: {', '.join(sorted(payload.values))}",
    )
    return {
        "ok": True,
        "data_id": written,
        "changed": sorted(payload.values),
        "fields": describe(get_settings(), RemoteDocuments() if remote_config_enabled() else None),
    }


__all__ = ["router"]
