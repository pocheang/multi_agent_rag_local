from __future__ import annotations

import json
import os
import tempfile
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings

_LOCK = threading.RLock()


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _default_path() -> Path:
    settings = get_settings()
    return settings.corpus_path.parent / "documents.jsonl"


def _normalize_record(row: dict[str, Any]) -> dict[str, Any]:
    out = dict(row)
    out.setdefault("document_id", "")
    out.setdefault("version", 1)
    out.setdefault("latest_version", out.get("version", 1))
    out.setdefault("tenant_id", out.get("owner_user_id", ""))
    out.setdefault("source", "")
    out.setdefault("filename", "")
    out.setdefault("sha256", "")
    out.setdefault("owner_user_id", "")
    out.setdefault("acl_tags", [])
    out.setdefault("visibility", "private")
    out.setdefault("agent_class", "general")
    out.setdefault("parser_profile", "")
    out.setdefault("status", "pending")
    out.setdefault("stage", "uploaded")
    out.setdefault("error", "")
    out.setdefault("chunks_indexed", 0)
    out.setdefault("triplets_written", 0)
    out.setdefault("created_at", _now_iso())
    out.setdefault("updated_at", out["created_at"])
    return out


def _new_document_id() -> str:
    """Create an identity independent from a mutable filesystem path."""

    return f"doc-{uuid.uuid4().hex}"


def _read_document_records(target: Path) -> list[dict[str, Any]]:
    if not target.exists():
        return []
    rows: list[dict[str, Any]] = []
    with target.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(_normalize_record(json.loads(line)))
    return rows


def _write_document_records(target: Path, records: list[dict[str, Any]]) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=target.parent,
            prefix=f".{target.name}.",
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
            for row in records:
                handle.write(json.dumps(_normalize_record(row), ensure_ascii=False) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def list_document_records(path: Path | None = None) -> list[dict[str, Any]]:
    target = path or _default_path()
    with _LOCK:
        return _read_document_records(target)


def write_document_records(records: list[dict[str, Any]], path: Path | None = None) -> None:
    target = path or _default_path()
    with _LOCK:
        _write_document_records(target, records)


def get_document_by_source(source: str, path: Path | None = None) -> dict[str, Any] | None:
    source_value = str(source)
    target = path or _default_path()
    with _LOCK:
        for row in _read_document_records(target):
            if str(row.get("source", "")) == source_value:
                return row
        return None


def get_document_record(document_id: str, path: Path | None = None) -> dict[str, Any] | None:
    target = path or _default_path()
    with _LOCK:
        for row in _read_document_records(target):
            if str(row.get("document_id", "")) == str(document_id):
                return row
        return None


def create_document_record(
    *,
    source: str,
    filename: str,
    sha256: str,
    owner_user_id: str,
    visibility: str,
    agent_class: str,
    parser_profile: str = "",
    tenant_id: str = "",
    acl_tags: tuple[str, ...] = (),
    document_id: str | None = None,
    path: Path | None = None,
) -> dict[str, Any]:
    target = path or _default_path()
    source_value = str(source)
    now = _now_iso()
    with _LOCK:
        rows = _read_document_records(target)
        existing = next(
            (
                row
                for row in rows
                if (document_id and row.get("document_id") == document_id)
                or (
                    not document_id
                    and str(row.get("source", "")) == source_value
                    and str(row.get("owner_user_id", "")) == str(owner_user_id)
                    and str(row.get("tenant_id", "") or row.get("owner_user_id", ""))
                    == str(tenant_id or owner_user_id)
                )
            ),
            None,
        )
        stable_document_id = str(existing.get("document_id")) if existing else (document_id or _new_document_id())
        previous_version = int(existing.get("version", 1) or 1) if existing else 0
        latest_version = int(existing.get("latest_version", previous_version) or previous_version) if existing else 0
        version = latest_version + 1 if existing and str(existing.get("sha256", "")) != sha256 else max(1, previous_version)
        incoming = _normalize_record(
            {
                "document_id": stable_document_id,
                "version": version,
                "latest_version": max(latest_version, version),
                "tenant_id": tenant_id or (existing or {}).get("tenant_id") or owner_user_id,
                "source": source_value,
                "filename": filename,
                "sha256": sha256,
                "owner_user_id": owner_user_id,
                "acl_tags": list(acl_tags),
                "visibility": visibility,
                "agent_class": agent_class,
                "parser_profile": parser_profile,
                "status": "pending",
                "stage": "uploaded",
                "error": "",
                "chunks_indexed": 0,
                "triplets_written": 0,
                "created_at": (existing or {}).get("created_at") or now,
                "updated_at": now,
            }
        )
        replaced = False
        out: list[dict[str, Any]] = []
        for row in rows:
            if row["document_id"] == stable_document_id:
                out.append(incoming)
                replaced = True
            else:
                out.append(row)
        if not replaced:
            out.append(incoming)
        _write_document_records(target, out)
    return incoming


def update_document_record(
    document_id: str,
    fields: dict[str, Any],
    path: Path | None = None,
) -> dict[str, Any]:
    target = path or _default_path()
    with _LOCK:
        rows = _read_document_records(target)
        updated: dict[str, Any] | None = None
        out: list[dict[str, Any]] = []
        for row in rows:
            if row.get("document_id") == document_id:
                merged = _normalize_record({**row, **fields, "updated_at": _now_iso()})
                out.append(merged)
                updated = merged
            else:
                out.append(row)
        if updated is None:
            raise ValueError(f"document not found: {document_id}")
        _write_document_records(target, out)
        return updated


def update_document_by_source(source: str, fields: dict[str, Any], path: Path | None = None) -> dict[str, Any]:
    target = path or _default_path()
    source_value = str(source)
    with _LOCK:
        rows = _read_document_records(target)
        updated: dict[str, Any] | None = None
        out: list[dict[str, Any]] = []
        for row in rows:
            if str(row.get("source", "")) == source_value:
                merged = _normalize_record({**row, **fields, "updated_at": _now_iso()})
                out.append(merged)
                updated = merged
            else:
                out.append(row)
        if updated is None:
            raise ValueError(f"document not found for source: {source}")
        _write_document_records(target, out)
        return updated


def delete_document_by_source(source: str, path: Path | None = None) -> bool:
    target = path or _default_path()
    source_value = str(source)
    with _LOCK:
        rows = _read_document_records(target)
        keep = [row for row in rows if str(row.get("source", "")) != source_value]
        if len(keep) == len(rows):
            return False
        _write_document_records(target, keep)
        return True


def merge_visible_document_status(
    indexed_rows: list[dict[str, Any]],
    *,
    user_id: str,
    role: str,
    approved_sources: set[str] | None = None,
) -> list[dict[str, Any]]:
    """Merge persisted document lifecycle status into visible index rows."""
    by_source = {str(row.get("source", "") or ""): dict(row) for row in indexed_rows}
    is_admin = str(role).lower() == "admin"
    approved = {str(source) for source in approved_sources} if approved_sources is not None else None
    for record in list_document_records():
        owner_user_id = str(record.get("owner_user_id", "") or "")
        visibility = str(record.get("visibility", "private") or "private").lower()
        source = str(record.get("source", "") or "")
        if approved is not None:
            if source not in approved:
                continue
        elif not is_admin and visibility != "public" and owner_user_id != str(user_id):
            continue
        if not source:
            continue
        row = by_source.get(
            source,
            {
                "filename": str(record.get("filename", "") or ""),
                "source": source,
                "chunks": 0,
                "pages": [],
                "page_count": 0,
                "in_uploads": Path(source).is_file(),
                "exists_on_disk": Path(source).is_file(),
            },
        )
        row["document_id"] = record.get("document_id")
        row["version"] = int(record.get("version", 1) or 1)
        row["latest_version"] = int(record.get("latest_version", record.get("version", 1)) or 1)
        row["tenant_id"] = str(record.get("tenant_id", "") or "")
        row["acl_tags"] = list(record.get("acl_tags", []) or [])
        row["owner_user_id"] = record.get("owner_user_id")
        row["visibility"] = record.get("visibility", "private")
        row["agent_class"] = record.get("agent_class", "general")
        row["indexing_status"] = record.get("status", "pending")
        row["indexing_stage"] = record.get("stage", "uploaded")
        row["indexing_error"] = record.get("error", "")
        row["triplets_written"] = int(record.get("triplets_written", 0) or 0)
        row["parser_profile"] = str(record.get("parser_profile", "") or "")
        if int(row.get("chunks", 0) or 0) == 0:
            row["chunks"] = int(record.get("chunks_indexed", 0) or 0)
        row["page_count"] = len(list(row.get("pages", []) or []))
        by_source[source] = row
    return sorted(
        by_source.values(), key=lambda row: (str(row.get("filename", "")).lower(), str(row.get("source", "")).lower())
    )
