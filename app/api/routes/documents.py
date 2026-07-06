"""Document management routes for the QueryMind API."""

import asyncio
try:
    import aiofiles
except ModuleNotFoundError:
    aiofiles = None
import logging
import time
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.api.dependencies import (
    _audit,
    settings,
    upload_limiter,
)
from app.api.utils.auth_dependencies import _require_permission, _require_user
from app.api.utils.auth_helpers import _client_ip
from app.api.utils.document_helpers import (
    _guess_agent_class_for_upload,
    _is_probably_valid_upload_signature,
    _is_source_manageable_for_user,
    _list_visible_documents_for_user,
)
from app.api.utils.error_responses import (
    bad_request,
    conflict,
    forbidden,
    internal_error,
    not_found,
    payload_too_large,
    rate_limited,
)
from app.api.utils.string_utils import normalize_string
from app.core.schemas import (
    FileIndexActionResponse,
    IndexedFileSummary,
    IndexHealthResponse,
    UploadResponse,
)
from app.ingestion.loaders import IMAGE_EXTENSIONS
from app.services.document_dedup import compute_sha256, find_duplicate_for_user
from app.services.document_registry import (
    create_document_record,
    delete_document_by_source,
    list_document_records,
    update_document_by_source,
)
from app.services.index_health import build_index_health_report
from app.services.index_manager import delete_file_index, list_indexed_files, rebuild_file_index, should_skip_reindex
from app.services.ingest_queue import enqueue_ingest_job
from app.services.parser_profiles import choose_parser_profile
from app.services.runtime_ops import append_index_freshness

router = APIRouter(tags=["documents"])
logger = logging.getLogger(__name__)


async def _write_file_bytes(target: Path, chunks: list[bytes]) -> None:
    """Write uploaded bytes using aiofiles when available, else a thread fallback."""
    if aiofiles is not None:
        async with aiofiles.open(target, "wb") as out:
            for chunk in chunks:
                await out.write(chunk)
        return

    payload = b"".join(chunks)
    await asyncio.to_thread(target.write_bytes, payload)


def _resolve_manageable_source_for_filename(filename: str, user: dict[str, Any]) -> str | None:
    """Resolve the current user's manageable source path from a frontend filename."""
    candidates: list[str] = []
    for row in _list_visible_documents_for_user(user):
        row_filename = str(row.get("filename", "") or "").strip()
        row_source = str(row.get("source", "") or "").strip()
        if row_filename != filename or not row_source:
            continue
        if _is_source_manageable_for_user(row_source, user):
            candidates.append(row_source)
    if len(candidates) == 1:
        return candidates[0]
    return None


def _merge_registry_status(indexed_rows: list[dict[str, Any]], user: dict[str, Any]) -> list[dict[str, Any]]:
    by_source = {str(row.get("source", "") or ""): dict(row) for row in indexed_rows}
    user_id = str(user.get("user_id", ""))
    role = str(user.get("role", "viewer")).lower()
    for record in list_document_records():
        owner_user_id = str(record.get("owner_user_id", "") or "")
        visibility = str(record.get("visibility", "private") or "private").lower()
        if role != "admin" and visibility != "public" and owner_user_id != user_id:
            continue
        source = str(record.get("source", "") or "")
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
        by_source.values(), key=lambda x: (str(x.get("filename", "")).lower(), str(x.get("source", "")).lower())
    )


def _sha256_file(path: Path) -> str:
    return compute_sha256(path)


@router.get("/documents", response_model=list[IndexedFileSummary])
def list_documents(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "document:read", request, "document")
    rows = _list_visible_documents_for_user(user)
    return _merge_registry_status(rows, user)


@router.delete("/documents/{filename}", response_model=FileIndexActionResponse)
def delete_document(
    filename: str,
    request: Request,
    remove_file: bool = False,
    source: str | None = None,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "document:manage_own", request, "document", resource_id=filename)
    source = normalize_string(source) or _resolve_manageable_source_for_filename(filename, user)
    if source is None:
        raise bad_request("source is required")
    if not _is_source_manageable_for_user(source, user):
        _audit(
            request,
            action="document.delete",
            resource_type="document",
            result="denied",
            user=user,
            resource_id=filename,
        )
        raise forbidden("source not allowed")
    try:
        result = FileIndexActionResponse(**delete_file_index(filename, remove_physical_file=remove_file, source=source))
        if remove_file:
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
        _audit(
            request,
            action="document.delete",
            resource_type="document",
            result="success",
            user=user,
            resource_id=filename,
        )
        return result
    except ValueError as e:
        _audit(
            request,
            action="document.delete",
            resource_type="document",
            result="failed",
            user=user,
            resource_id=filename,
            detail=str(e),
        )
        raise conflict(str(e))


@router.post("/documents/{filename}/reindex", response_model=FileIndexActionResponse)
def reindex_document(
    filename: str, request: Request, source: str | None = None, user: dict[str, Any] = Depends(_require_user)
):
    _require_permission(user, "document:manage_own", request, "document", resource_id=filename)
    source = normalize_string(source) or _resolve_manageable_source_for_filename(filename, user)
    if source is None:
        raise bad_request("source is required")
    if not _is_source_manageable_for_user(source, user):
        _audit(
            request,
            action="document.reindex",
            resource_type="document",
            result="denied",
            user=user,
            resource_id=filename,
        )
        raise forbidden("source not allowed")
    try:
        t0 = time.perf_counter()
        source_path = Path(source)
        if should_skip_reindex(source_path):
            return FileIndexActionResponse(
                ok=True,
                filename=filename,
                chunks_indexed=0,
                triplets_written=0,
                skipped=True,
                reason="unchanged_file_hash",
            )
        visibility = "private"
        owner_user_id = str(user.get("user_id", ""))
        agent_class = "general"
        parser_profile_name = ""
        for row in list_indexed_files():
            if str(row.get("source", "") or "") == source:
                visibility = str(row.get("visibility", visibility) or visibility)
                owner_user_id = str(row.get("owner_user_id", owner_user_id) or owner_user_id)
                agent_class = str(row.get("agent_class", agent_class) or agent_class)
                parser_profile_name = str(row.get("parser_profile", "") or parser_profile_name)
                break
        try:
            update_document_by_source(
                source,
                {
                    "status": "indexing",
                    "stage": "reindexing",
                    "error": "",
                    "sha256": _sha256_file(source_path),
                    "parser_profile": parser_profile_name,
                },
            )
        except ValueError:
            pass
        metadata_overrides_by_source = {
            source: {
                "owner_user_id": owner_user_id,
                "visibility": visibility,
                "agent_class": agent_class,
                "parser_profile": parser_profile_name,
            }
        }
        result = FileIndexActionResponse(
            **rebuild_file_index(
                filename,
                source=source,
                metadata_overrides_by_source=metadata_overrides_by_source,
            )
        )
        append_index_freshness(
            {
                "user_id": str(user.get("user_id", "")),
                "filename": filename,
                "source": source,
                "freshness_seconds": round((time.perf_counter() - t0), 4),
                "chunks_indexed": int(result.chunks_indexed or 0),
                "mode": "reindex",
            }
        )
        _audit(
            request,
            action="document.reindex",
            resource_type="document",
            result="success",
            user=user,
            resource_id=filename,
        )
        return result
    except ValueError as e:
        _audit(
            request,
            action="document.reindex",
            resource_type="document",
            result="failed",
            user=user,
            resource_id=filename,
            detail=str(e),
        )
        raise conflict(str(e))
    except FileNotFoundError as e:
        _audit(
            request,
            action="document.reindex",
            resource_type="document",
            result="failed",
            user=user,
            resource_id=filename,
            detail=str(e),
        )
        raise not_found(str(e))


@router.get("/documents/index-health", response_model=IndexHealthResponse)
def document_index_health(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "admin:ops_manage", request, "admin")
    report = build_index_health_report()
    return report


@router.post("/upload", response_model=UploadResponse)
async def upload_files(
    request: Request,
    files: list[UploadFile] = File(...),
    visibility: Annotated[str, Form()] = "private",
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "upload:create", request, "document")

    # Rate limiting: prevent storage abuse
    limiter_key = f"upload:{user['user_id']}:{_client_ip(request)}"
    if not upload_limiter.allow(limiter_key):
        _audit(request, action="upload.create", resource_type="document", result="rate_limited", user=user)
        raise rate_limited("Upload rate limit exceeded. Maximum 20 uploads per hour.")

    if len(files) > settings.upload_max_files:
        raise bad_request(f"too many files, max={settings.upload_max_files}")

    saved_paths: list[Path] = []
    filenames: list[str] = []
    skipped_files: list[str] = []
    requested_visibility = str(visibility or "private").strip().lower()
    if requested_visibility not in {"private", "public"}:
        requested_visibility = "private"
    role = str(user.get("role", "viewer")).lower()
    visibility_applied = requested_visibility if role == "admin" else "private"
    assigned_agent_classes: dict[str, str] = {}
    file_hashes_by_source: dict[str, str] = {}
    parser_profiles_by_source: dict[str, dict[str, Any]] = {}
    duplicate_files: list[str] = []
    reused_document_ids: list[str] = []
    total_uploaded_bytes = 0
    read_chunk = max(16 * 1024, int(settings.upload_read_chunk_bytes))
    user_upload_root = settings.uploads_path / user["user_id"]
    user_upload_root.mkdir(parents=True, exist_ok=True)

    for f in files:
        if not f.filename:
            continue

        # Security: Sanitize filename to prevent path traversal
        raw_filename = Path(f.filename).name
        safe_filename = raw_filename.replace("/", "").replace("\\", "").replace("..", "")

        # Reject hidden files and invalid filenames
        if not safe_filename or safe_filename.startswith(".") or safe_filename.startswith("_"):
            skipped_files.append(raw_filename)
            continue

        suffix = Path(safe_filename).suffix.lower()
        if suffix not in {".txt", ".md", ".pdf", *IMAGE_EXTENSIONS}:
            skipped_files.append(safe_filename)
            continue

        target = user_upload_root / safe_filename
        file_uploaded_bytes = 0
        file_head = b""
        file_chunks = []

        try:
            # Read and validate file before writing to disk (security improvement)
            while True:
                chunk = await f.read(read_chunk)
                if not chunk:
                    break
                if len(file_head) < 16:
                    file_head = (file_head + chunk)[:16]
                file_uploaded_bytes += len(chunk)
                total_uploaded_bytes += len(chunk)
                if file_uploaded_bytes > settings.upload_max_file_bytes:
                    raise payload_too_large(f"file too large: {target.name}")
                if total_uploaded_bytes > settings.upload_max_total_bytes:
                    raise payload_too_large("total upload size exceeded")
                file_chunks.append(chunk)
        finally:
            await f.close()

        if file_uploaded_bytes <= 0:
            continue

        # Validate file signature BEFORE writing to disk (prevents malicious files from touching filesystem)
        if suffix in {".pdf", *IMAGE_EXTENSIONS} and not _is_probably_valid_upload_signature(suffix, file_head):
            raise bad_request(f"invalid file signature: {safe_filename}")

        # Now write validated file to disk
        try:
            await _write_file_bytes(target, file_chunks)
        except Exception as e:
            if target.exists():
                target.unlink()
            raise internal_error(f"Failed to write file: {safe_filename}") from e
        sha256 = compute_sha256(target)
        duplicate = find_duplicate_for_user(sha256, str(user.get("user_id", "")))
        if duplicate is not None:
            duplicate_files.append(safe_filename)
            if duplicate.get("document_id"):
                reused_document_ids.append(str(duplicate.get("document_id", "")))
            if target.exists():
                target.unlink()
            continue
        saved_paths.append(target)
        filenames.append(safe_filename)
        assigned_agent_classes[str(target)] = _guess_agent_class_for_upload(safe_filename)
        file_hashes_by_source[str(target)] = sha256
        parser_profiles_by_source[str(target)] = choose_parser_profile(target, assigned_agent_classes[str(target)])

    if not saved_paths:
        if duplicate_files and not skipped_files:
            _audit(
                request,
                action="document.upload",
                resource_type="document",
                result="success",
                user=user,
                detail="duplicates_reused",
            )
            return UploadResponse(
                filenames=[],
                skipped_files=[],
                visibility_applied=visibility_applied,
                assigned_agent_classes={},
                document_ids=[],
                indexing_status="reused",
                duplicate_files=duplicate_files,
                reused_document_ids=[x for x in reused_document_ids if x],
                loaded_documents=0,
                chunks_indexed=0,
                triplets_written=0,
            )
        detail = "no supported files uploaded"
        if skipped_files:
            detail = f"{detail}; skipped={','.join(skipped_files)}"
        if duplicate_files:
            detail = f"{detail}; duplicates={','.join(duplicate_files)}"
        raise bad_request(detail)

    try:
        for target in saved_paths:
            delete_file_index(target.name, remove_physical_file=False, source=str(target))
    except Exception as e:
        _audit(
            request,
            action="document.upload",
            resource_type="document",
            result="failed",
            user=user,
            detail=f"pre-clean failed: {e}",
        )
        raise internal_error("upload pre-clean failed")

    try:
        document_ids: list[str] = []
        for p in saved_paths:
            parser_profile = parser_profiles_by_source.get(str(p), {})
            record = create_document_record(
                source=str(p),
                filename=p.name,
                sha256=file_hashes_by_source[str(p)],
                owner_user_id=str(user.get("user_id", "")),
                visibility=visibility_applied,
                agent_class=assigned_agent_classes.get(str(p), "general"),
                parser_profile=str(parser_profile.get("name", "") or ""),
            )
            document_ids.append(str(record["document_id"]))
            metadata_overrides = {
                "owner_user_id": str(user.get("user_id", "")),
                "visibility": visibility_applied,
                "agent_class": assigned_agent_classes.get(str(p), "general"),
                "parser_profile": str(parser_profile.get("name", "") or ""),
            }
            enqueue_ingest_job(
                document_id=str(record["document_id"]),
                path=p,
                metadata_overrides=metadata_overrides,
                parser_profile=parser_profile,
            )
            append_index_freshness(
                {
                    "user_id": str(user.get("user_id", "")),
                    "filename": p.name,
                    "source": str(p),
                    "freshness_seconds": 0.0,
                    "chunks_indexed": 0,
                    "mode": "queued",
                }
            )
    except Exception as e:
        _audit(request, action="document.upload", resource_type="document", result="failed", user=user, detail=str(e))
        raise internal_error("upload ingest failed")
    _audit(
        request,
        action="document.upload",
        resource_type="document",
        result="success",
        user=user,
        detail=",".join(filenames),
    )
    return UploadResponse(
        filenames=filenames,
        skipped_files=skipped_files,
        visibility_applied=visibility_applied,
        assigned_agent_classes=assigned_agent_classes,
        document_ids=document_ids,
        indexing_status="queued",
        duplicate_files=duplicate_files,
        reused_document_ids=[x for x in reused_document_ids if x],
        loaded_documents=len(saved_paths),
        chunks_indexed=0,
        triplets_written=0,
    )



