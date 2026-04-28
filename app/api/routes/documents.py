"""Document management routes for the Multi-Agent Local RAG API."""
import logging
import time
from pathlib import Path
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile

from app.api.dependencies import (
    _audit,
    _guess_agent_class_for_upload,
    _is_probably_valid_upload_signature,
    _is_source_manageable_for_user,
    _list_visible_documents_for_user,
    _require_user,
    _require_permission,
    settings,
)
from app.core.schemas import (
    FileIndexActionResponse,
    IndexedFileSummary,
    UploadResponse,
)
from app.ingestion.loaders import IMAGE_EXTENSIONS
from app.services.index_manager import delete_file_index, list_indexed_files, rebuild_file_index
from app.services.ingest_service import ingest_paths
from app.services.runtime_ops import append_index_freshness

router = APIRouter(tags=["documents"])
logger = logging.getLogger(__name__)


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


@router.get("/documents", response_model=list[IndexedFileSummary])
def list_documents(request: Request, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "document:read", request, "document")
    return _list_visible_documents_for_user(user)


@router.delete("/documents/{filename}", response_model=FileIndexActionResponse)
def delete_document(
    filename: str,
    request: Request,
    remove_file: bool = False,
    source: str | None = None,
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "document:manage_own", request, "document", resource_id=filename)
    source = (source or "").strip() or _resolve_manageable_source_for_filename(filename, user)
    if source is None:
        raise HTTPException(status_code=400, detail="source is required")
    if not _is_source_manageable_for_user(source, user):
        _audit(request, action="document.delete", resource_type="document", result="denied", user=user, resource_id=filename)
        raise HTTPException(status_code=403, detail="source not allowed")
    try:
        result = FileIndexActionResponse(**delete_file_index(filename, remove_physical_file=remove_file, source=source))
        _audit(request, action="document.delete", resource_type="document", result="success", user=user, resource_id=filename)
        return result
    except ValueError as e:
        _audit(request, action="document.delete", resource_type="document", result="failed", user=user, resource_id=filename, detail=str(e))
        raise HTTPException(status_code=409, detail=str(e))


@router.post("/documents/{filename}/reindex", response_model=FileIndexActionResponse)
def reindex_document(filename: str, request: Request, source: str | None = None, user: dict[str, Any] = Depends(_require_user)):
    _require_permission(user, "document:manage_own", request, "document", resource_id=filename)
    source = (source or "").strip() or _resolve_manageable_source_for_filename(filename, user)
    if source is None:
        raise HTTPException(status_code=400, detail="source is required")
    if not _is_source_manageable_for_user(source, user):
        _audit(request, action="document.reindex", resource_type="document", result="denied", user=user, resource_id=filename)
        raise HTTPException(status_code=403, detail="source not allowed")
    try:
        t0 = time.perf_counter()
        visibility = "private"
        owner_user_id = str(user.get("user_id", ""))
        agent_class = "general"
        for row in list_indexed_files():
            if str(row.get("source", "") or "") == source:
                visibility = str(row.get("visibility", visibility) or visibility)
                owner_user_id = str(row.get("owner_user_id", owner_user_id) or owner_user_id)
                agent_class = str(row.get("agent_class", agent_class) or agent_class)
                break
        metadata_overrides_by_source = {
            source: {
                "owner_user_id": owner_user_id,
                "visibility": visibility,
                "agent_class": agent_class,
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
        _audit(request, action="document.reindex", resource_type="document", result="success", user=user, resource_id=filename)
        return result
    except ValueError as e:
        _audit(request, action="document.reindex", resource_type="document", result="failed", user=user, resource_id=filename, detail=str(e))
        raise HTTPException(status_code=409, detail=str(e))
    except FileNotFoundError as e:
        _audit(request, action="document.reindex", resource_type="document", result="failed", user=user, resource_id=filename, detail=str(e))
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/upload", response_model=UploadResponse)
async def upload_files(
    request: Request,
    files: list[UploadFile] = File(...),
    visibility: Annotated[str, Form()] = "private",
    user: dict[str, Any] = Depends(_require_user),
):
    _require_permission(user, "upload:create", request, "document")
    if len(files) > settings.upload_max_files:
        raise HTTPException(status_code=400, detail=f"too many files, max={settings.upload_max_files}")

    saved_paths: list[Path] = []
    filenames: list[str] = []
    skipped_files: list[str] = []
    requested_visibility = str(visibility or "private").strip().lower()
    if requested_visibility not in {"private", "public"}:
        requested_visibility = "private"
    role = str(user.get("role", "viewer")).lower()
    visibility_applied = requested_visibility if role == "admin" else "private"
    assigned_agent_classes: dict[str, str] = {}
    total_uploaded_bytes = 0
    read_chunk = max(16 * 1024, int(settings.upload_read_chunk_bytes))
    user_upload_root = settings.uploads_path / user["user_id"]
    user_upload_root.mkdir(parents=True, exist_ok=True)

    for f in files:
        if not f.filename:
            continue
        suffix = Path(f.filename).suffix.lower()
        if suffix not in {".txt", ".md", ".pdf", *IMAGE_EXTENSIONS}:
            skipped_files.append(Path(f.filename).name)
            continue
        target = user_upload_root / Path(f.filename).name
        file_uploaded_bytes = 0
        file_head = b""
        try:
            with target.open("wb") as out:
                while True:
                    chunk = await f.read(read_chunk)
                    if not chunk:
                        break
                    if len(file_head) < 16:
                        file_head = (file_head + chunk)[:16]
                    file_uploaded_bytes += len(chunk)
                    total_uploaded_bytes += len(chunk)
                    if file_uploaded_bytes > settings.upload_max_file_bytes:
                        raise HTTPException(status_code=413, detail=f"file too large: {target.name}")
                    if total_uploaded_bytes > settings.upload_max_total_bytes:
                        raise HTTPException(status_code=413, detail="total upload size exceeded")
                    out.write(chunk)
        except HTTPException:
            if target.exists():
                target.unlink()
            raise
        finally:
            await f.close()

        if file_uploaded_bytes <= 0:
            if target.exists():
                target.unlink()
            continue
        if suffix in {".pdf", *IMAGE_EXTENSIONS} and not _is_probably_valid_upload_signature(suffix, file_head):
            if target.exists():
                target.unlink()
            raise HTTPException(status_code=400, detail=f"invalid file signature: {target.name}")
        saved_paths.append(target)
        filenames.append(target.name)
        assigned_agent_classes[str(target)] = _guess_agent_class_for_upload(target.name)

    if not saved_paths:
        detail = "no supported files uploaded"
        if skipped_files:
            detail = f"{detail}; skipped={','.join(skipped_files)}"
        raise HTTPException(status_code=400, detail=detail)

    try:
        for target in saved_paths:
            delete_file_index(target.name, remove_physical_file=False, source=str(target))
    except Exception as e:
        _audit(request, action="document.upload", resource_type="document", result="failed", user=user, detail=f"pre-clean failed: {e}")
        raise HTTPException(status_code=500, detail="upload pre-clean failed")

    ingest_started = time.perf_counter()
    try:
        metadata_overrides_by_source = {
            str(p): {
                "owner_user_id": str(user.get("user_id", "")),
                "visibility": visibility_applied,
                "agent_class": assigned_agent_classes.get(str(p), "general"),
            }
            for p in saved_paths
        }
        result = ingest_paths(
            saved_paths,
            reset_vector_store=False,
            metadata_overrides_by_source=metadata_overrides_by_source,
        )
    except Exception as e:
        _audit(request, action="document.upload", resource_type="document", result="failed", user=user, detail=str(e))
        raise HTTPException(status_code=500, detail="upload ingest failed")
    ingest_elapsed = (time.perf_counter() - ingest_started)
    per_file = ingest_elapsed / max(1, len(saved_paths))
    chunks_by_source = {str(row.get("source", "") or ""): int(row.get("chunks", 0) or 0) for row in list_indexed_files()}
    for p in saved_paths:
        append_index_freshness(
            {
                "user_id": str(user.get("user_id", "")),
                "filename": p.name,
                "source": str(p),
                "freshness_seconds": round(per_file, 4),
                "chunks_indexed": int(chunks_by_source.get(str(p), 0) or 0),
            }
        )
    _audit(request, action="document.upload", resource_type="document", result="success", user=user, detail=",".join(filenames))
    return UploadResponse(
        filenames=filenames,
        skipped_files=skipped_files,
        visibility_applied=visibility_applied,
        assigned_agent_classes=assigned_agent_classes,
        **result,
    )
