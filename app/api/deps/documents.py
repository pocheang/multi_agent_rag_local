"""
Document-related helper functions for the QueryMind API.
"""

import hashlib
import json
import logging
import re
from pathlib import Path
from typing import Any

from fastapi import Request

from app.core.config import get_settings
from app.ingestion.loaders import IMAGE_EXTENSIONS
from app.services.agent_classifier import classify_agent_class
from app.services.security.access_scope import list_visible_document_rows

logger = logging.getLogger(__name__)


settings = get_settings()


def _is_source_allowed_for_user(source: str | None, user: dict[str, Any]) -> bool:
    """Check if a source is allowed for the user."""
    if not source:
        return False
    source_path = Path(source).resolve()
    uploads_root = (settings.uploads_path / user["user_id"]).resolve()
    return uploads_root in source_path.parents


def _is_source_manageable_for_user(source: str | None, user: dict[str, Any]) -> bool:
    """Check if a source is manageable by the user."""
    if not source:
        return False
    role = str(user.get("role", "viewer")).lower()
    source_path = Path(source).resolve()
    if role == "admin":
        uploads_root = settings.uploads_path.resolve()
        return uploads_root in source_path.parents
    uploads_root = (settings.uploads_path / user["user_id"]).resolve()
    return uploads_root in source_path.parents


def _list_visible_documents_for_user(user: dict[str, Any]) -> list[dict[str, Any]]:
    """List all documents visible to the user."""
    return list_visible_document_rows(user, settings=settings)


def _allowed_sources_for_user(user: dict[str, Any]) -> list[str]:
    """Get all allowed sources for the user."""
    allowed: list[str] = []
    for row in _list_visible_documents_for_user(user):
        source = str(row.get("source", "") or "").strip()
        if source and source not in allowed:
            allowed.append(source)
    return allowed


def _allowed_sources_for_visible_filenames(user: dict[str, Any], filenames: list[str]) -> list[str]:
    """Get allowed sources for specific filenames."""
    wanted = {str(x or "").strip() for x in filenames if str(x or "").strip()}
    if not wanted:
        return []
    allowed: list[str] = []
    for row in _list_visible_documents_for_user(user):
        if str(row.get("filename", "") or "") not in wanted:
            continue
        source = str(row.get("source", "") or "").strip()
        if source and source not in allowed:
            allowed.append(source)
    return allowed


def _source_mtime_ns(source: str) -> int:
    """Get the modification time of a source file in nanoseconds."""
    try:
        path = Path(source)
        if path.exists() and path.is_file():
            return int(path.stat().st_mtime_ns)
    except (OSError, ValueError) as e:
        # File access error or invalid path
        logger.debug(f"Cannot get mtime for {source}: {e}")
        return 0
    return 0


def _visible_index_fingerprint_for_user(user: dict[str, Any]) -> str:
    """Generate a fingerprint of the visible index for the user."""
    rows = []
    for row in _list_visible_documents_for_user(user):
        source = str(row.get("source", "") or "").strip()
        rows.append(
            {
                "source": source,
                "chunks": int(row.get("chunks", 0) or 0),
                "owner_user_id": str(row.get("owner_user_id", "") or ""),
                "visibility": str(row.get("visibility", "") or ""),
                "agent_class": str(row.get("agent_class", "") or ""),
                "mtime_ns": _source_mtime_ns(source),
            }
        )
    raw = json.dumps(sorted(rows, key=lambda x: x["source"]), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _enforce_result_source_scope(
    result: dict[str, Any], allowed_sources: list[str], request: Request, user: dict[str, Any], audit_fn
) -> dict[str, Any]:
    """Compatibility adapter for callers that still import the old API helper."""
    from app.orchestration.compatibility_post_execution import enforce_result_source_scope

    return enforce_result_source_scope(
        result,
        allowed_sources,
        audit=lambda outcome, detail: audit_fn(
            request,
            action="query.source_scope",
            resource_type="query",
            result=outcome,
            user=user,
            detail=detail,
        ),
    )


def _resynthesize_after_source_scope(
    result: dict[str, Any],
    *,
    question: str,
    memory_context: str,
    use_reasoning: bool,
) -> dict[str, Any]:
    """Compatibility adapter for callers that still import the old API helper."""
    from app.orchestration.compatibility_post_execution import resynthesize_after_source_scope

    return resynthesize_after_source_scope(
        result,
        question=question,
        memory_context=memory_context,
        use_reasoning=use_reasoning,
    )


def _list_visible_pdf_names_for_user(user: dict[str, Any]) -> list[str]:
    """List visible PDF and image filenames for the user."""
    supported = {".pdf", *IMAGE_EXTENSIONS}
    names: list[str] = []
    for row in _list_visible_documents_for_user(user):
        filename = str(row.get("filename", "") or "").strip()
        if Path(filename).suffix.lower() not in supported:
            continue
        if filename not in names:
            names.append(filename)
    return names


def _visible_doc_chunks_by_filename_for_user(user: dict[str, Any]) -> dict[str, int]:
    """Get chunk counts by filename for visible documents."""
    mapping: dict[str, int] = {}
    for row in _list_visible_documents_for_user(user):
        filename = str(row.get("filename", "") or "").strip()
        if not filename:
            continue
        try:
            chunks = int(row.get("chunks", 0) or 0)
        except (ValueError, TypeError):
            # Invalid chunk count, default to 0
            chunks = 0
        if filename not in mapping:
            mapping[filename] = chunks
        else:
            mapping[filename] = max(mapping[filename], chunks)
    return mapping


_FILE_INVENTORY_RE = re.compile(r"(几个|多少|数量|有哪些|列表|清单|列出|多少个)")
_FILE_TARGET_RE = re.compile(r"(文件|文档|pdf|资料|上传)")


def _is_file_inventory_question(question: str) -> bool:
    """Check if the question is asking for file inventory."""
    q = (question or "").strip().lower()
    if not q:
        return False
    return bool(_FILE_TARGET_RE.search(q) and _FILE_INVENTORY_RE.search(q))


def _build_user_file_inventory_answer(user: dict[str, Any]) -> str:
    """Build an answer listing the user's accessible files."""
    visible = _list_visible_documents_for_user(user)
    total = len(visible)
    if total == 0:
        return "你当前可访问的文件数量为 0。"
    names: list[str] = []
    for row in visible:
        name = str(row.get("filename", "") or "").strip()
        if name and name not in names:
            names.append(name)
    preview = "、".join(names[:20])
    more = ""
    if len(names) > 20:
        more = f"（其余 {len(names) - 20} 个已省略）"
    return f"你当前可访问的文件共 {len(names)} 个：{preview}{more}。"


def _guess_agent_class_for_upload(filename: str) -> str:
    """Guess the agent class for an uploaded file."""
    suffix = Path(filename).suffix.lower()
    if suffix in {".pdf", *IMAGE_EXTENSIONS}:
        return "pdf_text"
    guessed = classify_agent_class(Path(filename).stem)
    return (
        guessed
        if guessed in {"general", "cybersecurity", "artificial_intelligence", "pdf_text", "policy"}
        else "general"
    )


def _is_probably_valid_upload_signature(suffix: str, head: bytes) -> bool:
    """Check if the file signature matches the extension."""
    prefix = (head or b"")[:16]
    if suffix == ".pdf":
        return prefix.startswith(b"%PDF-")
    if suffix == ".png":
        return prefix.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix in {".jpg", ".jpeg"}:
        return prefix.startswith(b"\xff\xd8\xff")
    if suffix == ".gif":
        return prefix.startswith(b"GIF87a") or prefix.startswith(b"GIF89a")
    if suffix == ".bmp":
        return prefix.startswith(b"BM")
    if suffix in {".tif", ".tiff"}:
        return prefix.startswith(b"II*\x00") or prefix.startswith(b"MM\x00*")
    if suffix == ".webp":
        return len(prefix) >= 12 and prefix.startswith(b"RIFF") and prefix[8:12] == b"WEBP"
    return True
