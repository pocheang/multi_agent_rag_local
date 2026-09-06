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
    error_responses,
    internal_error,
    not_found,
    rate_limited,
)
from app.api.utils.auth_helpers import _client_ip
from app.api.utils.string_utils import normalize_string
from app.ingestion.loaders import IMAGE_EXTENSIONS, OFFICE_EXTENSIONS
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
from app.services.security.audit_actions import AuditAction
from app.services.security.rbac import Permission

router = APIRouter(tags=["documents"])


def _manageable_rows(user: dict[str, Any]) -> list[dict[str, Any]]:
    """Documents this caller can both see and act on."""
    return [
        row
        for row in _list_visible_documents_for_user(user)
        if str(row.get("source", "") or "").strip()
        and _is_source_manageable_for_user(str(row.get("source", "") or "").strip(), user)
    ]


def _resolve_manageable_document(
    filename: str,
    user: dict[str, Any],
    source: str | None = None,
) -> dict[str, Any] | None:
    """Resolve the one document this request may act on, or None.

    `source` *narrows* the candidates; it does not select one. It used to be
    taken at face value:

        source = normalize_string(source) or _resolve_manageable_source_for_filename(...)

    which skipped the visibility rules entirely whenever the caller supplied
    `?source=`, leaving only a directory check. See P0-3 in
    docs/superpowers/plans/2026-08-29-user-data-isolation.md.

    Returns the whole row, not just the path, so the caller can audit which
    document -- and whose -- it acted on.
    """
    candidates = [row for row in _manageable_rows(user) if str(row.get("filename", "") or "").strip() == filename]
    if source:
        candidates = [row for row in candidates if str(row.get("source", "") or "").strip() == source]
    return candidates[0] if len(candidates) == 1 else None


def _resolve_manageable_document_by_id(document_id: str, user: dict[str, Any]) -> dict[str, Any] | None:
    """Resolve a document by its immutable id.

    Filenames are not identifiers: two users routinely hold a `report.pdf`, so
    the filename form has to refuse whenever it is ambiguous. `document_id`
    (`doc-{uuid4}`, assigned at registration) always names exactly one.
    """
    candidates = [row for row in _manageable_rows(user) if str(row.get("document_id", "") or "").strip() == document_id]
    return candidates[0] if len(candidates) == 1 else None


def _document_audit_detail(row: dict[str, Any]) -> str:
    """Identify the document and its owner, so a cross-user action is legible."""
    return (
        f"document_id={str(row.get('document_id', '') or '') or 'unknown'}; "
        f"owner_user_id={str(row.get('owner_user_id', '') or '') or 'unknown'}; "
        f"source={str(row.get('source', '') or '')}"
    )


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
    _require_permission(user, Permission.DOCUMENT_READ, request, "document")
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
    """Delete by filename. Refuses when the name is ambiguous -- prefer by-id."""
    _require_permission(user, Permission.DOCUMENT_MANAGE_OWN, request, "document", resource_id=filename)
    row = _resolve_manageable_document(filename, user, normalize_string(source))
    return _perform_delete(row, filename, request, user, remove_file)


@router.delete("/documents/by-id/{document_id}", response_model=FileIndexActionResponse)
def delete_document_by_id(
    document_id: str,
    request: Request,
    remove_file: bool = False,
    user: dict[str, Any] = Depends(_require_user),
):
    """Delete by immutable id. Unambiguous where a filename is not."""
    _require_permission(user, Permission.DOCUMENT_MANAGE_OWN, request, "document", resource_id=document_id)
    row = _resolve_manageable_document_by_id(document_id, user)
    filename = str((row or {}).get("filename", "") or "")
    return _perform_delete(row, filename, request, user, remove_file)


@router.post("/documents/{filename}/reindex", response_model=FileIndexActionResponse)
def reindex_document(
    filename: str, request: Request, source: str | None = None, user: dict[str, Any] = Depends(_require_user)
):
    """Reindex by filename. Refuses when the name is ambiguous -- prefer by-id."""
    _require_permission(user, Permission.DOCUMENT_MANAGE_OWN, request, "document", resource_id=filename)
    row = _resolve_manageable_document(filename, user, normalize_string(source))
    return _perform_reindex(row, filename, request, user)


@router.post("/documents/by-id/{document_id}/reindex", response_model=FileIndexActionResponse)
def reindex_document_by_id(document_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
    """Reindex by immutable id. Unambiguous where a filename is not."""
    _require_permission(user, Permission.DOCUMENT_MANAGE_OWN, request, "document", resource_id=document_id)
    row = _resolve_manageable_document_by_id(document_id, user)
    filename = str((row or {}).get("filename", "") or "")
    return _perform_reindex(row, filename, request, user)


def _deny_unresolved(action: str, request: Request, user: dict[str, Any], resource_id: str):
    """One refusal for 'no such document' and 'not yours'.

    Deliberately identical either way: telling an unauthorized caller that the
    document exists but belongs to someone else is itself a disclosure.
    """
    _audit(
        request,
        action=action,
        resource_type="document",
        result="denied",
        user=user,
        resource_id=resource_id,
    )
    raise not_found("Document")


def _perform_delete(
    row: dict[str, Any] | None,
    filename: str,
    request: Request,
    user: dict[str, Any],
    remove_file: bool,
) -> FileIndexActionResponse:
    if row is None:
        _deny_unresolved(AuditAction.DOCUMENT_DELETE, request, user, filename)
    source = str(row.get("source", "") or "")
    try:
        _require_registered_filename_source(filename, source)
        result = FileIndexActionResponse(
            **delete_document_index(filename, remove_physical_file=remove_file, source=source)
        )
        _audit(
            request,
            action=AuditAction.DOCUMENT_DELETE,
            resource_type="document",
            result="success",
            user=user,
            resource_id=filename,
            detail=_document_audit_detail(row),
        )
        return result
    except ValueError as e:
        _audit(
            request,
            action=AuditAction.DOCUMENT_DELETE,
            resource_type="document",
            result="failed",
            user=user,
            resource_id=filename,
            detail=f"{_document_audit_detail(row)}; error={e}",
        )
        raise conflict(str(e))


def _perform_reindex(
    row: dict[str, Any] | None,
    filename: str,
    request: Request,
    user: dict[str, Any],
) -> FileIndexActionResponse:
    if row is None:
        _deny_unresolved(AuditAction.DOCUMENT_REINDEX, request, user, filename)
    source = str(row.get("source", "") or "")
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
            action=AuditAction.DOCUMENT_REINDEX,
            resource_type="document",
            result="success",
            user=user,
            resource_id=filename,
            detail=_document_audit_detail(row),
        )
        return result
    except ValueError as e:
        _audit(
            request,
            action=AuditAction.DOCUMENT_REINDEX,
            resource_type="document",
            result="failed",
            user=user,
            resource_id=filename,
            detail=f"{_document_audit_detail(row)}; error={e}",
        )
        raise conflict(str(e))


@router.get("/documents/index-health", response_model=IndexHealthResponse)
def document_index_health(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, Permission.ADMIN_OPS_MANAGE, request, "admin")
    report = build_index_health_report()
    return report


@router.post("/upload", response_model=UploadResponse, responses=error_responses(413))
async def upload_files(
    request: Request,
    files: list[UploadFile] = File(...),
    visibility: Annotated[str, Form()] = "private",
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, Permission.UPLOAD_CREATE, request, "document")
    limiter_key = f"upload:{user['user_id']}:{_client_ip(request)}"
    if not upload_limiter.try_acquire(limiter_key):
        _audit(request, action=AuditAction.UPLOAD_CREATE, resource_type="document", result="rate_limited", user=user)
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
            supported_suffixes={".txt", ".md", ".pdf", *IMAGE_EXTENSIONS, *OFFICE_EXTENSIONS},
            signature_suffixes={".pdf", *IMAGE_EXTENSIONS, *OFFICE_EXTENSIONS},
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
            error_details["suggestion"] = (
                f"本次上传总大小 {error_details['total_size_mb']}MB 超过限制 {error_details['max_total_size_mb']}MB，请分批上传"
            )

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
                action=AuditAction.DOCUMENT_UPLOAD,
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
            action=AuditAction.DOCUMENT_UPLOAD,
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
            tenant_id=str(user.get("tenant_id", "") or user.get("user_id", "")),
            acl_tags=tuple(str(value) for value in user.get("acl_tags", ()) or ()),
        )
    except Exception as e:
        _audit(
            request,
            action=AuditAction.DOCUMENT_UPLOAD,
            resource_type="document",
            result="failed",
            user=user,
            detail=str(e),
        )
        raise internal_error("upload ingest failed")
    _audit(
        request,
        action=AuditAction.DOCUMENT_UPLOAD,
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
