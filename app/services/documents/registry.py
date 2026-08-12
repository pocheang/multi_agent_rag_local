from __future__ import annotations

import hashlib
import json
import threading
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
    out.setdefault("source", "")
    out.setdefault("filename", "")
    out.setdefault("sha256", "")
    out.setdefault("owner_user_id", "")
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


def _document_id_for(source: str, owner_user_id: str) -> str:
    seed = f"{owner_user_id}|{source}"
    return f"doc-{hashlib.sha1(seed.encode('utf-8')).hexdigest()[:16]}"


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
    with target.open("w", encoding="utf-8") as f:
        for row in records:
            f.write(json.dumps(_normalize_record(row), ensure_ascii=False) + "\n")


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


def create_document_record(
    *,
    source: str,
    filename: str,
    sha256: str,
    owner_user_id: str,
    visibility: str,
    agent_class: str,
    parser_profile: str = "",
    path: Path | None = None,
) -> dict[str, Any]:
    target = path or _default_path()
    source_value = str(source)
    document_id = _document_id_for(source_value, str(owner_user_id))
    now = _now_iso()
    incoming = _normalize_record(
        {
            "document_id": document_id,
            "source": source_value,
            "filename": filename,
            "sha256": sha256,
            "owner_user_id": owner_user_id,
            "visibility": visibility,
            "agent_class": agent_class,
            "parser_profile": parser_profile,
            "status": "pending",
            "stage": "uploaded",
            "error": "",
            "chunks_indexed": 0,
            "triplets_written": 0,
            "created_at": now,
            "updated_at": now,
        }
    )
    with _LOCK:
        rows = _read_document_records(target)
        replaced = False
        out: list[dict[str, Any]] = []
        for row in rows:
            if row["document_id"] == document_id or row["source"] == source_value:
                incoming["created_at"] = row.get("created_at") or incoming["created_at"]
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
