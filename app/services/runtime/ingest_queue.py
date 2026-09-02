from __future__ import annotations

import atexit
import logging
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any

from app.services.documents.ingest import ingest_paths
from app.services.documents.registry import create_document_record, update_document_record
from app.services.runtime.runtime_ops import append_index_freshness

logger = logging.getLogger(__name__)

_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="ingest")
_JOBS: dict[str, Future] = {}


def _cleanup_completed_jobs() -> None:
    """Remove completed jobs from the _JOBS dict to prevent unbounded growth."""
    completed_ids = [doc_id for doc_id, future in _JOBS.items() if future.done()]
    for doc_id in completed_ids:
        del _JOBS[doc_id]
    if completed_ids:
        logger.debug(f"Cleaned up {len(completed_ids)} completed ingest jobs")


def shutdown_ingest_queue(wait: bool = True) -> None:
    """
    Gracefully shutdown the ingest queue thread pool.

    Args:
        wait: If True, wait for all pending jobs to complete
    """
    global _EXECUTOR
    logger.info(f"Shutting down ingest queue (wait={wait}, pending_jobs={len(_JOBS)})")
    _EXECUTOR.shutdown(wait=wait)
    _JOBS.clear()


# Register cleanup on application exit
atexit.register(lambda: shutdown_ingest_queue(wait=False))


def run_ingest_job(
    *,
    document_id: str,
    path: Path,
    metadata_overrides: dict[str, Any],
    parser_profile: dict[str, Any] | None = None,
) -> dict[str, Any]:
    update_document_record(document_id, {"status": "indexing", "stage": "loading", "error": ""})
    source = str(path)
    try:
        result = ingest_paths(
            [path],
            reset_vector_store=False,
            metadata_overrides_by_source={source: metadata_overrides},
            parser_profiles_by_source={source: parser_profile or {}},
        )
        updated = update_document_record(
            document_id,
            {
                "status": "ready",
                "stage": "complete",
                "error": "",
                "chunks_indexed": int(result.get("chunks_indexed", 0) or 0),
                "triplets_written": int(result.get("triplets_written", 0) or 0),
            },
        )
        return {"ok": True, "result": result, "document": updated}
    except Exception as exc:
        logger.exception("ingest_job_failed document_id=%s path=%s", document_id, path)
        update_document_record(
            document_id,
            {"status": "failed", "stage": "failed", "error": str(exc)},
        )
        return {"ok": False, "error": str(exc)}


def enqueue_ingest_job(
    *,
    document_id: str,
    path: Path,
    metadata_overrides: dict[str, Any],
    parser_profile: dict[str, Any] | None = None,
) -> bool:
    # Clean up completed jobs to prevent unbounded memory growth
    _cleanup_completed_jobs()

    future = _EXECUTOR.submit(
        run_ingest_job,
        document_id=document_id,
        path=path,
        metadata_overrides=metadata_overrides,
        parser_profile=parser_profile,
    )
    _JOBS[document_id] = future
    return True


def register_and_enqueue_uploads(
    *,
    uploads: list[Any],
    owner_user_id: str,
    visibility: str,
    tenant_id: str = "",
    acl_tags: tuple[str, ...] = (),
) -> list[str]:
    """Create document records and enqueue their ingestion as one runtime operation."""
    document_ids: list[str] = []
    for upload in uploads:
        parser_profile = upload.parser_profile
        record = create_document_record(
            source=str(upload.path),
            filename=upload.filename,
            sha256=upload.sha256,
            owner_user_id=owner_user_id,
            visibility=visibility,
            agent_class=upload.agent_class,
            parser_profile=str(parser_profile.get("name", "") or ""),
            tenant_id=tenant_id or owner_user_id,
            acl_tags=acl_tags,
        )
        document_id = str(record["document_id"])
        document_ids.append(document_id)
        enqueue_ingest_job(
            document_id=document_id,
            path=upload.path,
            metadata_overrides={
                "owner_user_id": owner_user_id,
                "tenant_id": str(record.get("tenant_id", "") or tenant_id or owner_user_id),
                "document_id": document_id,
                "version": int(record.get("version", 1) or 1),
                "acl_tags": tuple(str(value) for value in record.get("acl_tags", ()) or ()),
                "visibility": visibility,
                "agent_class": upload.agent_class,
                "parser_profile": str(parser_profile.get("name", "") or ""),
            },
            parser_profile=parser_profile,
        )
        append_index_freshness(
            {
                "user_id": owner_user_id,
                "filename": upload.filename,
                "source": str(upload.path),
                "freshness_seconds": 0.0,
                "chunks_indexed": 0,
                "mode": "queued",
            }
        )
    return document_ids
