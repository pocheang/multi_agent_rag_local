from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.retrievers.stores.corpus import read_corpus_records, write_corpus_records
from app.retrievers.stores.parent import read_parent_records, write_parent_records
from app.services.documents.dedup import compute_sha256
from app.services.documents.registry import delete_document_by_source, get_document_by_source, update_document_by_source
from app.services.runtime.runtime_ops import append_index_freshness

logger = logging.getLogger(__name__)


def _record_source(record: dict[str, Any]) -> str:
    meta = record.get("metadata", {}) or {}
    source = str(meta.get("source", "")).strip()
    return source


def _record_source_name(record: dict[str, Any]) -> str:
    source = _record_source(record)
    return Path(source).name if source else ""


def _require_registered_filename_source(filename: str, source: str) -> dict[str, Any]:
    """Require the explicit source to be the registered document named by filename."""
    record = get_document_by_source(source)
    if record is None:
        raise ValueError(f"source is not registered: {source}")
    if Path(source).name != filename or str(record.get("filename", "") or "") != filename:
        raise ValueError("filename does not match registered source")
    return record


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
                "indexing_status": "ready",
                "indexing_stage": "complete",
                "indexing_error": "",
                "triplets_written": 0,
                "parser_profile": str(meta.get("parser_profile", "") or ""),
            },
        )
        entry["chunks"] += 1
        if not entry.get("owner_user_id") and meta.get("owner_user_id"):
            entry["owner_user_id"] = meta.get("owner_user_id")
        if str(meta.get("visibility", "")).strip():
            entry["visibility"] = str(meta.get("visibility"))
        if str(meta.get("agent_class", "")).strip():
            entry["agent_class"] = str(meta.get("agent_class"))
        if str(meta.get("parser_profile", "")).strip():
            entry["parser_profile"] = str(meta.get("parser_profile"))
        page = meta.get("page")
        if page is not None:
            try:
                entry["pages"].add(int(page))
            except (ValueError, TypeError):
                pass

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
                "indexing_status": "pending",
                "indexing_stage": "uploaded",
                "indexing_error": "",
                "triplets_written": 0,
                "parser_profile": "",
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
                "indexing_status": "pending",
                "indexing_stage": "uploaded",
                "indexing_error": "",
                "triplets_written": 0,
                "parser_profile": "",
            },
        )
        entry["exists_on_disk"] = True
        entry["source"] = str(path)

    items = []
    for entry in by_file.values():
        entry["pages"] = sorted(entry["pages"])
        entry["page_count"] = len(entry["pages"])
        items.append(entry)
    items.sort(key=lambda x: (x["filename"].lower(), str(x.get("source", "")).lower()))
    return items


def _delete_triplets_by_sources(sources: list[str]) -> int:
    try:
        from app.graph.knowledge.client import Neo4jClient
    except ImportError:
        logger.debug("Neo4j client not available, skipping triplet deletion")
        return 0

    removed = 0
    try:
        client = Neo4jClient()
    except (RuntimeError, ValueError) as e:
        logger.warning(f"Failed to create Neo4j client: {e}")
        return 0
    try:
        for source_key in sources:
            try:
                removed += client.delete_by_source(source_key)
            except (RuntimeError, ValueError) as e:
                logger.warning(f"Failed to delete triplets for source {source_key}: {e}")
                continue
    finally:
        client.close()
    return removed


def _delete_vector_documents(ids: list[str]) -> None:
    if not ids:
        return
    from app.retrievers.stores.vector import delete_documents_by_ids

    delete_documents_by_ids(ids)


def _reset_bm25() -> None:
    from app.retrievers.bm25_retriever import reset_bm25_cache

    reset_bm25_cache()


def _reset_retrieval_cache() -> None:
    from app.retrievers.hybrid.retriever import clear_retrieval_cache

    clear_retrieval_cache()


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
    _reset_retrieval_cache()

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
                delete_document_by_source(str(candidate))

    return {
        "ok": True,
        "filename": filename,
        "chunks_removed": len(removed),
        "vector_ids_removed": len(removed_ids),
        "triplets_removed": triplets_removed,
        "file_removed": file_removed,
    }


def delete_document_index(filename: str, *, source: str, remove_physical_file: bool) -> dict[str, Any]:
    """Delete a document's index and synchronize its persisted lifecycle status."""
    _require_registered_filename_source(filename, source)
    result = delete_file_index(filename, remove_physical_file=remove_physical_file, source=source)
    if remove_physical_file:
        delete_document_by_source(source)
    else:
        try:
            update_document_by_source(
                source,
                {
                    "status": "pending",
                    "stage": "uploaded",
                    "error": "",
                    "chunks_indexed": 0,
                    "triplets_written": 0,
                },
            )
        except ValueError:
            pass
    return result


def prepare_uploaded_document_indexes(paths: list[Path]) -> None:
    """Clear stale index data for files that have just been replaced in storage."""
    for path in paths:
        delete_file_index(path.name, remove_physical_file=False, source=str(path))


def should_skip_reindex(path: Path, registry_path: Path | None = None) -> bool:
    record = get_document_by_source(str(path), path=registry_path)
    if record is None:
        return False
    if not path.exists() or not path.is_file():
        return False
    current_hash = compute_sha256(path)
    return str(record.get("sha256", "")) == current_hash and str(record.get("status", "")) == "ready"


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

    from app.services.documents.ingest import ingest_paths

    result = ingest_paths(
        [path],
        reset_vector_store=False,
        metadata_overrides_by_source=metadata_overrides_by_source,
    )
    try:
        update_document_by_source(
            str(path),
            {
                "status": "ready",
                "stage": "complete",
                "error": "",
                "chunks_indexed": int(result.get("chunks_indexed", 0) or 0),
                "triplets_written": int(result.get("triplets_written", 0) or 0),
                "sha256": compute_sha256(path),
            },
        )
    except ValueError:
        pass
    result["filename"] = filename
    result["ok"] = True
    return result


def rebuild_document_index(filename: str, *, source: str, user_id: str) -> dict[str, Any]:
    """Rebuild one document using its current index metadata and lifecycle record."""
    started_at = time.perf_counter()
    source_path = Path(source)
    record = _require_registered_filename_source(filename, source)
    if should_skip_reindex(source_path):
        return {
            "ok": True,
            "filename": filename,
            "chunks_indexed": 0,
            "triplets_written": 0,
            "skipped": True,
            "reason": "unchanged_file_hash",
        }

    visibility = str(record.get("visibility", "private") or "private")
    owner_user_id = str(record.get("owner_user_id", user_id) or user_id)
    agent_class = str(record.get("agent_class", "general") or "general")
    parser_profile_name = str(record.get("parser_profile", "") or "")
    try:
        update_document_by_source(
            source,
            {
                "status": "indexing",
                "stage": "reindexing",
                "error": "",
                "sha256": compute_sha256(source_path),
                "parser_profile": parser_profile_name,
            },
        )
    except ValueError:
        pass

    result = rebuild_file_index(
        filename,
        source=source,
        metadata_overrides_by_source={
            source: {
                "owner_user_id": owner_user_id,
                "visibility": visibility,
                "agent_class": agent_class,
                "parser_profile": parser_profile_name,
            }
        },
    )
    append_index_freshness(
        {
            "user_id": str(user_id),
            "filename": filename,
            "source": source,
            "freshness_seconds": round((time.perf_counter() - started_at), 4),
            "chunks_indexed": int(result.get("chunks_indexed", 0) or 0),
            "mode": "reindex",
        }
    )
    return result


def rebuild_all_vector_index() -> dict[str, Any]:
    from app.retrievers.stores.vector import reset_vector_store_from_records

    records = read_corpus_records()
    reset_vector_store_from_records(records)
    _reset_bm25()
    _reset_retrieval_cache()
    return {"ok": True, "records_reindexed": len(records)}
