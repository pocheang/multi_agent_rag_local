"""
API routes for session export and import.

POST /api/v1/sessions/{id}/export    - Export session
POST /api/v1/sessions/import         - Import session
"""

import json
import logging
import uuid
import zipfile
from dataclasses import asdict
from io import BytesIO

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.dependencies import _history_store_for_user, _require_user, _require_valid_session_id
from app.api.transport.errors import error_responses
from app.core.config import get_settings
from app.services.sessions.export import (
    ConflictStrategy,
    ExportFormat,
    SessionExportService,
)
from app.services.sessions.metadata import normalize_description, normalize_tags
from app.services.sessions.service import get_metadata_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["session-export"])


# ============================================================================
# Request/Response Models
# ============================================================================


class ExportRequest(BaseModel):
    """Request model for session export."""

    format: ExportFormat = Field(default="json", description="Export format (json/zip)")
    include_context: bool = Field(default=True, description="Include context tracking data")


class ExportResponse(BaseModel):
    """Response model for export metadata."""

    session_id: str
    format: ExportFormat
    size_bytes: int
    created_at: str


class ImportRequest(BaseModel):
    """Request model for session import."""

    conflict_strategy: ConflictStrategy = Field(
        default="skip",
        description="How to handle existing session (skip/overwrite/rename)",
    )


class ImportResponse(BaseModel):
    """Response model for import result."""

    session_id: str
    original_session_id: str
    conflict_occurred: bool
    conflict_resolution: str | None
    messages_imported: int
    metadata_imported: bool
    context_imported: bool


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/{session_id}/export", responses=error_responses(404, 500))
async def export_session(
    session_id: str,
    request: ExportRequest,
    user: dict = Depends(_require_user),
):
    """
    Export session to JSON or ZIP format.

    Returns the exported data as a downloadable file.
    """
    session_id = _require_valid_session_id(session_id)
    user_id = str(user.get("user_id", "") or "")
    service = SessionExportService(metadata_service=get_metadata_service(user_id))

    try:
        session = _history_store_for_user(user).get_session(session_id)

        if session is None:
            raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

        # Get metadata
        # Get context if requested
        context_data = None
        if request.include_context:
            from app.services.context_management import get_context_service

            context_service = get_context_service()
            context = context_service.get_context(session_id)
            if context:
                context_data = {
                    "entities": [
                        {
                            "text": e.text,
                            "type": e.entity_type,
                            "confidence": e.confidence,
                            "mention_turn": e.mention_turn,
                        }
                        for e in context.entities
                    ],
                    "current_topic": context.current_topic,
                    "previous_topics": context.previous_topics,
                    "current_turn": context.current_turn,
                }

        # Export
        exported = service.export_session(
            session_id=session_id,
            messages=list(session.get("messages", []) or []),
            context=context_data,
        )

        json_data = json.dumps(asdict(exported), ensure_ascii=False, indent=2).encode("utf-8")
        if request.format == "json":
            export_data = json_data
        else:
            archive = BytesIO()
            with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zf:
                zf.writestr(f"{session_id}.json", json_data)
            export_data = archive.getvalue()

        # Determine content type and filename
        if request.format == "json":
            content_type = "application/json"
            filename = f"session_{session_id}.json"
        else:  # zip
            content_type = "application/zip"
            filename = f"session_{session_id}.zip"

        logger.info(f"Exported session {session_id} as {request.format} ({len(export_data)} bytes)")

        # Return as downloadable file
        return StreamingResponse(
            iter([export_data]),
            media_type=content_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Content-Length": str(len(export_data)),
            },
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception(f"Failed to export session {session_id}")
        raise HTTPException(status_code=500, detail="Export failed")


@router.post("/import", response_model=ImportResponse, responses=error_responses(400, 409, 413, 500))
async def import_session(
    file: UploadFile = File(..., description="Exported session file (JSON or ZIP)"),
    conflict_strategy: ConflictStrategy = "skip",
    user: dict = Depends(_require_user),
):
    """
    Import session from exported file.

    Handles conflicts based on the specified strategy:
    - skip: Keep existing session, don't import
    - overwrite: Replace existing session with imported data
    - rename: Import with a new session ID (append timestamp)
    """
    try:
        max_bytes = int(getattr(get_settings(), "upload_max_file_bytes", 20 * 1024 * 1024))
        file_data = await file.read(max_bytes + 1)
        if len(file_data) > max_bytes:
            raise HTTPException(status_code=413, detail="Session import file is too large")

        # Determine format from filename
        filename = str(file.filename or "").lower()
        if filename.endswith(".zip"):
            try:
                with zipfile.ZipFile(BytesIO(file_data), "r") as zf:
                    candidates = [info for info in zf.infolist() if info.filename.lower().endswith(".json")]
                    if len(candidates) != 1 or candidates[0].file_size > max_bytes:
                        raise HTTPException(status_code=400, detail="ZIP must contain one bounded JSON session")
                    json_data = zf.read(candidates[0])
            except zipfile.BadZipFile:
                raise HTTPException(status_code=400, detail="Invalid ZIP session export")
        elif filename.endswith(".json"):
            json_data = file_data
        else:
            raise HTTPException(
                status_code=400,
                detail="Unsupported file format. Expected .json or .zip",
            )

        try:
            imported = json.loads(json_data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid session JSON: {exc}")
        if not isinstance(imported, dict) or imported.get("export_version") != "1.0":
            raise HTTPException(status_code=400, detail="Unsupported or missing export version")

        original_session_id = _require_valid_session_id(str(imported.get("session_id", "")))
        raw_messages = imported.get("messages", [])
        raw_metadata = imported.get("metadata")
        if not isinstance(raw_messages, list) or not isinstance(raw_metadata, dict):
            raise HTTPException(status_code=400, detail="Invalid session export structure")
        messages: list[dict] = []
        for message in raw_messages:
            if not isinstance(message, dict):
                raise HTTPException(status_code=400, detail="Invalid message in session export")
            role = str(message.get("role", "") or "").strip()
            content = str(message.get("content", "") or "")
            if role not in {"user", "assistant", "system"}:
                raise HTTPException(status_code=400, detail="Invalid message role in session export")
            message_metadata = message.get("metadata") or {}
            if not isinstance(message_metadata, dict):
                raise HTTPException(status_code=400, detail="Invalid message metadata in session export")
            messages.append({"role": role, "content": content, "metadata": dict(message_metadata)})

        raw_tags = raw_metadata.get("tags") or []
        raw_description = raw_metadata.get("description")
        raw_category = raw_metadata.get("category")
        if not isinstance(raw_tags, list) or not all(isinstance(tag, str) for tag in raw_tags):
            raise HTTPException(status_code=400, detail="Invalid metadata tags in session export")
        if raw_description is not None and not isinstance(raw_description, str):
            raise HTTPException(status_code=400, detail="Invalid metadata description in session export")
        if raw_category not in {None, "work", "personal", "research", "learning", "development", "analysis", "other"}:
            raise HTTPException(status_code=400, detail="Invalid metadata category in session export")
        try:
            metadata_tags = normalize_tags(raw_tags)
            metadata_description = normalize_description(raw_description)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))

        history_store = _history_store_for_user(user)
        metadata_service = get_metadata_service(str(user.get("user_id", "") or ""))
        existing = history_store.get_session(original_session_id)
        session_id = original_session_id
        conflict_occurred = existing is not None
        conflict_resolution = None
        if conflict_occurred:
            if conflict_strategy == "skip":
                raise HTTPException(status_code=409, detail="Session already exists")
            if conflict_strategy == "rename":
                session_id = uuid.uuid4().hex
                conflict_resolution = "renamed"
            else:
                history_store.delete_session(session_id)
                metadata_service.delete_metadata(session_id)
                conflict_resolution = "overwritten"

        history_store.create_session(session_id=session_id)
        for message in messages:
            history_store.append_message(
                session_id,
                message["role"],
                message["content"],
                metadata=message["metadata"],
            )
        metadata_service.create_metadata(
            session_id=session_id,
            tags=metadata_tags,
            category=raw_category,
            description=metadata_description,
        )

        logger.info(f"Imported session {session_id} (original: {original_session_id}, conflict: {conflict_occurred})")

        return ImportResponse(
            session_id=session_id,
            original_session_id=original_session_id,
            conflict_occurred=conflict_occurred,
            conflict_resolution=conflict_resolution,
            messages_imported=len(messages),
            metadata_imported=True,
            context_imported=False,
        )

    except HTTPException:
        raise
    except Exception:
        logger.exception("Failed to import session")
        raise HTTPException(status_code=500, detail="Import failed")
