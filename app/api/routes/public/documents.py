"""Public document management routes for the QueryMind API."""

from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.api.dependencies import (
    _audit,
    settings,
    upload_limiter,
)
from app.api.deps.auth import _require_permission, _require_user
from app.api.deps.documents import (
    _guess_agent_class_for_upload,
    _is_probably_valid_upload_signature,
    _is_source_manageable_for_user,
    _list_visible_documents_for_user,
)
from app.api.schemas import (
    FileIndexActionResponse,
    IndexedFileSummary,
    IndexHealthResponse,
    UploadResponse,
)
from app.api.transport.errors import (
    bad_request,
    conflict,
    forbidden,
    internal_error,
    not_found,
    rate_limited,
)
from app.api.utils.auth_helpers import _client_ip
from app.api.utils.string_utils import normalize_string
from app.ingestion.loaders import IMAGE_EXTENSIONS
from app.services.documents.dedup import (
    UploadInvalidFileError,
    UploadPayloadTooLargeError,
    UploadStorageError,
    UploadWriteError,
    store_uploaded_files,
)
from app.services.documents.index_health import build_index_health_report
from app.services.documents.index_manager import (
    delete_document_index,
    prepare_uploaded_document_indexes,
    rebuild_document_index,
)
from app.services.documents.registry import get_document_by_source, merge_visible_document_status
from app.services.parser_profiles import choose_parser_profile
from app.services.runtime.ingest_queue import register_and_enqueue_uploads

router = APIRouter(tags=["documents"])


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


def _require_registered_filename_source(filename: str, source: str) -> None:
    """Defend against a filename/source pair changing after route-level checks."""
    record = get_document_by_source(source)
    if record is None:
        raise ValueError(f"source is not registered: {source}")
    if Path(source).name != filename or str(record.get("filename", "") or "") != filename:
        raise ValueError("filename does not match registered source")


def _approved_upload_visibility(requested_visibility: str, user: dict[str, Any]) -> tuple[str, bool]:
    requested = (normalize_string(requested_visibility) or "private").lower()
    if requested not in {"private", "public"}:
        requested = "private"
    is_admin = str(user.get("role", "viewer")).lower() == "admin"
    return ("public" if requested == "public" and is_admin else "private", is_admin)


@router.get("/documents", response_model=list[IndexedFileSummary])
def list_documents(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "document:read", request, "document")
    rows = _list_visible_documents_for_user(user)
    return merge_visible_document_status(
        rows,
        user_id=str(user.get("user_id", "")),
        role=str(user.get("role", "viewer")),
        approved_sources={str(row.get("source", "") or "") for row in rows},
    )


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
        _require_registered_filename_source(filename, source)
        result = FileIndexActionResponse(
            **delete_document_index(filename, remove_physical_file=remove_file, source=source)
        )
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
        _require_registered_filename_source(filename, source)
        result = FileIndexActionResponse(
            **rebuild_document_index(
                filename,
                source=source,
                user_id=str(user.get("user_id", "")),
            )
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
    limiter_key = f"upload:{user['user_id']}:{_client_ip(request)}"
    if not upload_limiter.try_acquire(limiter_key):
        _audit(request, action="upload.create", resource_type="document", result="rate_limited", user=user)
        raise rate_limited("Upload rate limit exceeded. Maximum 20 uploads per hour.")

    visibility_applied, public_visibility_approved = _approved_upload_visibility(visibility, user)

    try:
        storage_result = await store_uploaded_files(
            files=files,
            owner_user_id=str(user["user_id"]),
            role=str(user.get("role", "viewer")),
            requested_visibility=visibility,
            visibility_applied=visibility_applied,
            public_visibility_approved=public_visibility_approved,
            uploads_path=settings.uploads_path,
            max_files=settings.upload_max_files,
            max_file_bytes=settings.upload_max_file_bytes,
            max_total_bytes=settings.upload_max_total_bytes,
            read_chunk_bytes=settings.upload_read_chunk_bytes,
            supported_suffixes={".txt", ".md", ".pdf", *IMAGE_EXTENSIONS},
            signature_suffixes={".pdf", *IMAGE_EXTENSIONS},
            is_valid_signature=_is_probably_valid_upload_signature,
            agent_class_for_upload=_guess_agent_class_for_upload,
            parser_profile_for_upload=choose_parser_profile,
        )
    except UploadPayloadTooLargeError as exc:
        # 构建友好的错误消息
        error_details = {
            "error": "upload_too_large",
            "message": str(exc),
        }

        # 添加具体的大小信息
        if exc.file_size and exc.max_file_size:
            error_details["file_size_mb"] = round(exc.file_size / (1024 * 1024), 2)
            error_details["max_file_size_mb"] = round(exc.max_file_size / (1024 * 1024), 2)
            error_details["suggestion"] = f"单个文件不能超过 {error_details['max_file_size_mb']}MB"

        if exc.total_size and exc.max_total_size:
            error_details["total_size_mb"] = round(exc.total_size / (1024 * 1024), 2)
            error_details["max_total_size_mb"] = round(exc.max_total_size / (1024 * 1024), 2)
            error_details["suggestion"] = f"本次上传总大小 {error_details['total_size_mb']}MB 超过限制 {error_details['max_total_size_mb']}MB，请分批上传"

        if exc.filename:
            error_details["filename"] = exc.filename

        raise HTTPException(status_code=413, detail=error_details)
    except UploadInvalidFileError as exc:
        raise bad_request(str(exc))
    except UploadWriteError as exc:
        raise internal_error(str(exc))
    except UploadStorageError as exc:
        raise bad_request(str(exc))

    if not storage_result.saved_uploads:
        if storage_result.duplicate_files and not storage_result.skipped_files:
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
                visibility_applied=storage_result.visibility_applied,
                assigned_agent_classes={},
                document_ids=[],
                indexing_status="reused",
                duplicate_files=storage_result.duplicate_files,
                reused_document_ids=[x for x in storage_result.reused_document_ids if x],
                loaded_documents=0,
                chunks_indexed=0,
                triplets_written=0,
            )
        detail = "no supported files uploaded"
        if storage_result.skipped_files:
            detail = f"{detail}; skipped={','.join(storage_result.skipped_files)}"
        if storage_result.duplicate_files:
            detail = f"{detail}; duplicates={','.join(storage_result.duplicate_files)}"
        raise bad_request(detail)

    try:
        prepare_uploaded_document_indexes([upload.path for upload in storage_result.saved_uploads])
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
        document_ids = register_and_enqueue_uploads(
            uploads=storage_result.saved_uploads,
            owner_user_id=str(user.get("user_id", "")),
            visibility=storage_result.visibility_applied,
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
        detail=",".join(upload.filename for upload in storage_result.saved_uploads),
    )
    return UploadResponse(
        filenames=[upload.filename for upload in storage_result.saved_uploads],
        skipped_files=storage_result.skipped_files,
        visibility_applied=storage_result.visibility_applied,
        assigned_agent_classes={str(upload.path): upload.agent_class for upload in storage_result.saved_uploads},
        document_ids=document_ids,
        indexing_status="queued",
        duplicate_files=storage_result.duplicate_files,
        reused_document_ids=[x for x in storage_result.reused_document_ids if x],
        loaded_documents=len(storage_result.saved_uploads),
        chunks_indexed=0,
        triplets_written=0,
    )
