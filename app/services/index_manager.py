from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.retrievers.corpus_store import read_corpus_records, write_corpus_records
from app.retrievers.parent_store import read_parent_records, write_parent_records


def _record_source(record: dict[str, Any]) -> str:
    meta = record.get("metadata", {}) or {}
    source = str(meta.get("source", "")).strip()
    return source


def _record_source_name(record: dict[str, Any]) -> str:
    source = _record_source(record)
    return Path(source).name if source else ""


def _select_records(
    records: list[dict[str, Any]],
    filename: str,
    source: str | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    filename_matches = [row for row in records if _record_source_name(row) == filename]
    if source is None:
        unique_sources = sorted({_record_source(row) for row in filename_matches if _record_source(row)})
        if len(unique_sources) > 1:
            raise ValueError(f"ambiguous filename '{filename}', provide source to disambiguate")
        removed = filename_matches
    else:
        removed = [row for row in filename_matches if _record_source(row) == source]
    removed_ids = {id(row) for row in removed}
    keep = [row for row in records if id(row) not in removed_ids]
    return removed, keep


def list_indexed_files() -> list[dict[str, Any]]:
    records = read_corpus_records()
    by_file: dict[str, dict[str, Any]] = {}
    for row in records:
        source = _record_source(row)
        name = _record_source_name(row)
        if not source and not name:
            continue
        meta = row.get("metadata", {}) or {}
        key = source or f"filename::{name}"
        entry = by_file.setdefault(
            key,
            {
                "filename": name,
                "source": source or meta.get("source", name),
                "chunks": 0,
                "pages": set(),
                "owner_user_id": meta.get("owner_user_id"),
                "visibility": str(meta.get("visibility", "private") or "private"),
                "agent_class": str(meta.get("agent_class", "general") or "general"),
                "in_uploads": False,
                "exists_on_disk": False,
            },
        )
        entry["chunks"] += 1
        if not entry.get("owner_user_id") and meta.get("owner_user_id"):
            entry["owner_user_id"] = meta.get("owner_user_id")
        if str(meta.get("visibility", "")).strip():
            entry["visibility"] = str(meta.get("visibility"))
        if str(meta.get("agent_class", "")).strip():
            entry["agent_class"] = str(meta.get("agent_class"))
        page = meta.get("page")
        if page is not None:
            entry["pages"].add(str(page))

    settings = get_settings()
    for path in settings.uploads_path.rglob("*"):
        if not path.is_file():
            continue
        key = str(path)
        entry = by_file.setdefault(
            key,
            {
                "filename": path.name,
                "source": str(path),
                "chunks": 0,
                "pages": set(),
                "owner_user_id": None,
                "visibility": "private",
                "agent_class": "general",
                "in_uploads": True,
                "exists_on_disk": True,
            },
        )
        entry["in_uploads"] = True
        entry["exists_on_disk"] = True
        entry["source"] = str(path)

    for path in settings.docs_path.rglob("*"):
        if not path.is_file():
            continue
        key = str(path)
        entry = by_file.setdefault(
            key,
            {
                "filename": path.name,
                "source": str(path),
                "chunks": 0,
                "pages": set(),
                "owner_user_id": None,
                "visibility": "private",
                "agent_class": "general",
                "in_uploads": False,
                "exists_on_disk": True,
            },
        )
        entry["exists_on_disk"] = True
        entry["source"] = str(path)

    items = []
    for entry in by_file.values():
        entry["pages"] = sorted(entry["pages"])
        items.append(entry)
    items.sort(key=lambda x: (x["filename"].lower(), str(x.get("source", "")).lower()))
    return items


def _delete_triplets_by_sources(sources: list[str]) -> int:
    try:
        from app.graph.neo4j_client import Neo4jClient
    except Exception:
        return 0

    removed = 0
    try:
        client = Neo4jClient()
    except Exception:
        return 0
    try:
        for source_key in sources:
            try:
                removed += client.delete_by_source(source_key)
            except Exception:
                continue
    finally:
        client.close()
    return removed


def _delete_vector_documents(ids: list[str]) -> None:
    if not ids:
        return
    from app.retrievers.vector_store import delete_documents_by_ids

    delete_documents_by_ids(ids)


def _reset_bm25() -> None:
    from app.retrievers.bm25_retriever import reset_bm25_cache

    reset_bm25_cache()


def _delete_parent_records(filename: str, source: str | None = None) -> int:
    parent_records = read_parent_records()
    removed, keep = _select_records(records=parent_records, filename=filename, source=source)
    write_parent_records(keep)
    return len(removed)


def delete_file_index(filename: str, remove_physical_file: bool = False, source: str | None = None) -> dict[str, Any]:
    records = read_corpus_records()
    removed, keep = _select_records(records=records, filename=filename, source=source)
    removed_ids: list[str] = []
    for row in removed:
        if row.get("id"):
            removed_ids.append(str(row["id"]))

    _delete_vector_documents(removed_ids)
    write_corpus_records(keep)
    _delete_parent_records(filename=filename, source=source)
    _reset_bm25()

    removed_sources = sorted({_record_source(row) for row in removed if _record_source(row)})
    source_keys = set(removed_sources)
    for source_value in removed_sources:
        source_keys.add(Path(source_value).name)
    triplets_removed = _delete_triplets_by_sources(sorted(source_keys))

    settings = get_settings()
    file_removed = False
    if remove_physical_file:
        candidates: list[Path] = []
        if source:
            candidates.append(Path(source))
        else:
            for item in removed_sources:
                candidates.append(Path(item))
            candidates.extend([settings.uploads_path / filename, settings.docs_path / filename])
        for candidate in candidates:
            if candidate.exists() and candidate.is_file():
                candidate.unlink()
                file_removed = True

    return {
        "ok": True,
        "filename": filename,
        "chunks_removed": len(removed),
        "vector_ids_removed": len(removed_ids),
        "triplets_removed": triplets_removed,
        "file_removed": file_removed,
    }


def rebuild_file_index(
    filename: str,
    source: str | None = None,
    metadata_overrides_by_source: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    delete_file_index(filename, remove_physical_file=False, source=source)
    settings = get_settings()
    if source:
        candidates = [Path(source)]
    else:
        candidates = [settings.uploads_path / filename, settings.docs_path / filename]
        candidates.extend([p for p in settings.docs_path.rglob(filename)])
    existing_map: dict[str, Path] = {}
    for p in candidates:
        if p.exists() and p.is_file():
            existing_map[str(p.resolve())] = p
    existing = list(existing_map.values())
    if source is None and len(existing) > 1:
        raise ValueError(f"ambiguous filename '{filename}', provide source to disambiguate")
    path = existing[0] if existing else None
    if path is None:
        raise FileNotFoundError(f"file not found on disk: {filename}")

    from app.services.ingest_service import ingest_paths

    result = ingest_paths(
        [path],
        reset_vector_store=False,
        metadata_overrides_by_source=metadata_overrides_by_source,
    )
    result["filename"] = filename
    result["ok"] = True
    return result


def rebuild_all_vector_index() -> dict[str, Any]:
    from app.retrievers.vector_store import reset_vector_store_from_records

    records = read_corpus_records()
    reset_vector_store_from_records(records)
    _reset_bm25()
    return {"ok": True, "records_reindexed": len(records)}
