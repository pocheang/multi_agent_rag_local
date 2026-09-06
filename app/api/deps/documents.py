"""
Document-related helper functions for the QueryMind API.
"""

import logging
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.ingestion.loaders import IMAGE_EXTENSIONS
from app.services.agent_classifier import classify_agent_class
from app.services.security.access_scope import list_visible_document_rows

logger = logging.getLogger(__name__)


settings = get_settings()


def _has_cross_tenant_rights(user: dict[str, Any]) -> bool:
    """Whether this actor may act on documents outside its own uploads.

    Mirrors the gate app/services/security/access_scope.py already applies to
    *reading* across tenants, so managing cannot reach further than listing.
    No caller grants these permissions today (the authenticated user dict is
    user_id/username/role/status/credit_balance), which is exactly the point:
    admins can neither see nor act on another user's documents until someone
    deliberately wires an admin flow that grants it.
    """
    if str(user.get("role", "viewer")).lower() != "admin":
        return False
    permissions = frozenset(str(value) for value in user.get("permissions", ()) or ())
    return "*" in permissions or "tenant:cross_read" in permissions


def _is_source_manageable_for_user(source: str | None, user: dict[str, Any]) -> bool:
    """Check if a source is manageable by the user.

    The admin branch used to grant the whole uploads root on the role alone, so
    `DELETE /documents/report.pdf?source=/uploads/bob/report.pdf` acted on Bob's
    file -- while the same admin could not even list it. See P0-3 in
    docs/superpowers/plans/2026-08-29-user-data-isolation.md.
    """
    if not source:
        return False
    source_path = Path(source).resolve()
    if _has_cross_tenant_rights(user):
        uploads_root = settings.uploads_path.resolve()
        return uploads_root in source_path.parents
    uploads_root = (settings.uploads_path / user["user_id"]).resolve()
    return uploads_root in source_path.parents


def _list_visible_documents_for_user(user: dict[str, Any]) -> list[dict[str, Any]]:
    """List all documents visible to the user."""
    return list_visible_document_rows(user, settings=settings)


def _allowed_sources_for_user(user: dict[str, Any]) -> list[str]:
    """Get all allowed sources for the user."""
    allowed: list[str] = []
    for row in _list_visible_documents_for_user(user):
        source = str(row.get("source", "") or "").strip()
        if source and source not in allowed:
            allowed.append(source)
    return allowed


def _guess_agent_class_for_upload(filename: str) -> str:
    """Guess the agent class for an uploaded file."""
    suffix = Path(filename).suffix.lower()
    if suffix in {".pdf", *IMAGE_EXTENSIONS}:
        return "pdf_text"
    guessed = classify_agent_class(Path(filename).stem)
    return (
        guessed
        if guessed in {"general", "cybersecurity", "artificial_intelligence", "pdf_text", "policy"}
        else "general"
    )


def _is_probably_valid_upload_signature(suffix: str, head: bytes) -> bool:
    """Check if the file signature matches the extension."""
    prefix = (head or b"")[:16]
    if suffix == ".pdf":
        return prefix.startswith(b"%PDF-")
    if suffix == ".png":
        return prefix.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".jpg", ".jpeg"}:
        return prefix.startswith(b"\xff\xd8\xff")
    if suffix == ".gif":
        return prefix.startswith(b"GIF87a") or prefix.startswith(b"GIF89a")
    if suffix == ".bmp":
        return prefix.startswith(b"BM")
    if suffix in {".tif", ".tiff"}:
        return prefix.startswith(b"II*\x00") or prefix.startswith(b"MM\x00*")
    if suffix == ".webp":
        return len(prefix) >= 12 and prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP"
    if suffix in {".docx", ".pptx", ".xlsx"}:
        return prefix.startswith(b"PK\x03\x04")
    if suffix == ".xls":
        return prefix.startswith(b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1")
    return True
