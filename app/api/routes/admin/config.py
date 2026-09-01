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

from app.api.application.config_reload import apply_config_reload
from app.api.dependencies import _audit, _require_permission, _require_user
from app.api.transport.errors import bad_request
from app.core.config import get_settings
from app.core.config_schema import describe, validate_values
from app.core.remote_config import RemoteDocuments, parse_properties, remote_config_enabled

logger = logging.getLogger(__name__)

router = APIRouter(tags=["admin", "config"])


class ConfigValues(BaseModel):
    """A partial change: only the fields the administrator actually edited."""

    values: dict[str, str] = Field(default_factory=dict)
    data_id: str | None = None


@router.get("/admin/config/schema")
def admin_config_schema(request: Request, user: dict[str, Any] = Depends(_require_user)):
    """Every editable field, its current value, and which layer supplied it."""

    _require_permission(user, "admin:ops_manage", request, "admin")
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

    _require_permission(user, "admin:ops_manage", request, "admin")
    if not payload.values:
        raise bad_request("no values to save")
    if not remote_config_enabled():
        raise bad_request("no configuration centre is configured; set NACOS_ENABLED and restart")

    try:
        accepted = validate_values(payload.values)
    except ValueError as exc:
        _audit(
            request,
            action="admin.config.save",
            resource_type="admin",
            result="failure",
            user=user,
            detail=f"rejected: {'; '.join(sorted(payload.values))}",
        )
        raise bad_request(str(exc)) from exc

    current = {row["alias"]: row for row in describe(get_settings())}
    pinned = sorted(alias for alias in accepted if not current.get(alias, {}).get("editable_here", True))
    if pinned:
        raise bad_request(f"pinned in the process environment, so the console cannot change them: {', '.join(pinned)}")

    documents = RemoteDocuments()
    known = documents.config.data_ids
    if payload.data_id is not None and payload.data_id not in known:
        raise bad_request(f"unknown data id: {payload.data_id}")

    current = {data_id: parse_properties(text) for data_id, text in documents.all().items()}
    fallback = payload.data_id or known[-1]

    # Each key goes back to the document that already defines it. Writing
    # everything to one document instead puts the same key in two places, where
    # the later id silently wins -- so the page would show a value from one
    # document, the edit would land in another, and the two would drift apart.
    # A key nothing defines yet goes to the fallback, which is the last id
    # precisely because later ids override earlier ones.
    routed: dict[str, dict[str, str]] = {}
    for alias, value in accepted.items():
        target = payload.data_id
        if target is None:
            owning = [data_id for data_id in known if alias in current.get(data_id, {})]
            target = owning[-1] if owning else fallback
        routed.setdefault(target, {})[alias] = value

    written: list[str] = []
    for data_id, changes in routed.items():
        merged = {**current.get(data_id, {}), **changes}
        try:
            published = documents.publish(data_id, merged)
        except Exception as exc:
            logger.exception("admin config: publish failed for %s", data_id)
            raise bad_request(f"the configuration centre rejected the write: {exc}") from exc
        if not published:
            raise bad_request(f"the configuration centre did not accept the write to {data_id}")
        written.append(data_id)

    apply_config_reload()
    _audit(
        request,
        action="admin.config.save",
        resource_type="admin",
        result="success",
        resource_id=",".join(sorted(written)),
        user=user,
        detail=f"changed: {', '.join(sorted(accepted))}",
    )
    return {
        "ok": True,
        "data_id": sorted(written),
        "changed": sorted(accepted),
        "fields": describe(get_settings(), documents),
    }


__all__ = ["router"]
