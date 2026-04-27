"""
Document-related helper functions for the Multi-Agent Local RAG API.
"""
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from fastapi import HTTPException, Request

from app.core.config import get_settings
from app.ingestion.loaders import IMAGE_EXTENSIONS
from app.services.agent_classifier import classify_agent_class
from app.services.index_manager import list_indexed_files
from app.services.rag_runtime_scope import is_under_path
from app.agents.synthesis_agent import synthesize_answer

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
    user_upload_root = (settings.uploads_path / user["user_id"]).resolve()
    docs_root = settings.docs_path.resolve()
    user_id = str(user.get("user_id", ""))
    items: list[dict[str, Any]] = []
    for row in list_indexed_files():
        source = str(row.get("source", "") or "")
        if not source:
            continue
        source_path = Path(source).resolve()
        # Treat curated data/docs content as a shared knowledge base.
        if is_under_path(source_path, docs_root):
            items.append(row)
            continue
        owner_user_id = str(row.get("owner_user_id", "") or "")
        visibility = str(row.get("visibility", "private") or "private").lower()
        if visibility == "public":
            items.append(row)
            continue
        if owner_user_id and owner_user_id == user_id:
            items.append(row)
            continue
        # Backward compatibility for legacy records without owner_user_id.
        if user_upload_root in source_path.parents:
            items.append(row)
    return items


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
    except Exception:
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


def _vector_context_from_citations(citations: list[dict[str, Any]]) -> str:
    """Build vector context from citations."""
    blocks = []
    for citation in citations:
        metadata = citation.get("metadata", {}) or {}
        source = str(citation.get("source", "") or Path(str(metadata.get("source", "") or "unknown")).name)
        retrieval_sources = metadata.get("retrieval_sources", [])
        if not isinstance(retrieval_sources, list):
            retrieval_sources = [str(retrieval_sources)]
        retrieval_label = ",".join(str(x) for x in retrieval_sources if str(x).strip()) or "filtered"
        blocks.append(
            f"[SOURCE: {source or 'unknown'}]\n"
            f"[RETRIEVAL: {retrieval_label}]\n"
            f"{str(citation.get('content', '') or '')}"
        )
    return "\n\n".join(blocks)


def _enforce_result_source_scope(
    result: dict[str, Any],
    allowed_sources: list[str],
    request: Request,
    user: dict[str, Any],
    audit_fn
) -> dict[str, Any]:
    """Enforce source scope on query results."""
    allowed_set = set(allowed_sources)
    source_scope = dict(result.get("source_scope", {}) or {})
    if not allowed_set:
        vector_result = dict(result.get("vector_result", {}) or {})
        denied = len(list(vector_result.get("citations", []) or []))
        vector_result["citations"] = []
        vector_result["context"] = ""
        vector_result["retrieved_count"] = 0
        vector_result["effective_hit_count"] = 0
        graph_result = dict(result.get("graph_result", {}) or {})
        graph_filtered = bool(
            graph_result.get("context")
            or graph_result.get("entities")
            or graph_result.get("neighbors")
            or graph_result.get("paths")
        )
        if graph_filtered:
            graph_result.update({"context": "", "entities": [], "neighbors": [], "paths": []})
        source_scope.update(
            {
                "checked": True,
                "allowed_source_count": 0,
                "filtered_vector_citations": denied,
                "filtered_graph": graph_filtered,
            }
        )
        out = dict(result)
        out["vector_result"] = vector_result
        out["graph_result"] = graph_result
        out["source_scope"] = source_scope
        audit_fn(
            request,
            action="query.source_scope",
            resource_type="query",
            result="denied",
            user=user,
            detail=f"no_allowed_sources; filtered_citations={denied}",
        )
        return out
    vector_result = dict(result.get("vector_result", {}) or {})
    citations = list(vector_result.get("citations", []) or [])
    kept = []
    denied = 0
    for c in citations:
        meta = c.get("metadata", {}) or {}
        src = str(meta.get("source", "") or "")
        if src and src in allowed_set:
            kept.append(c)
        else:
            denied += 1
    if denied > 0:
        audit_fn(
            request,
            action="query.source_scope",
            resource_type="query",
            result="denied",
            user=user,
            detail=f"filtered_citations={denied}",
        )
    else:
        audit_fn(
            request,
            action="query.source_scope",
            resource_type="query",
            result="success",
            user=user,
            detail=f"citations_checked={len(citations)}",
        )
    vector_result["citations"] = kept
    vector_result["retrieved_count"] = len(kept)
    vector_result["effective_hit_count"] = min(int(vector_result.get("effective_hit_count", len(kept)) or 0), len(kept))
    vector_result["context"] = _vector_context_from_citations(kept)
    source_scope.update(
        {
            "checked": True,
            "allowed_source_count": len(allowed_set),
            "filtered_vector_citations": denied,
            "filtered_graph": False,
        }
    )
    out = dict(result)
    out["vector_result"] = vector_result
    out["source_scope"] = source_scope
    return out


def _source_scope_needs_resynthesis(result: dict[str, Any]) -> bool:
    """Check if result needs resynthesis after source scope filtering."""
    scope = result.get("source_scope", {}) or {}
    return bool(scope.get("filtered_vector_citations", 0) or scope.get("filtered_graph", False))


def _resynthesize_after_source_scope(
    result: dict[str, Any],
    *,
    question: str,
    memory_context: str,
    use_reasoning: bool,
) -> dict[str, Any]:
    """Resynthesize answer after source scope filtering."""
    if not _source_scope_needs_resynthesis(result):
        return result
    vector_context = str((result.get("vector_result", {}) or {}).get("context", "") or "")
    graph_context = str((result.get("graph_result", {}) or {}).get("context", "") or "")
    web_context = str((result.get("web_result", {}) or {}).get("context", "") or "")
    answer = synthesize_answer(
        question=question,
        skill_name=str(result.get("skill", "") or "answer_with_citations"),
        memory_context=memory_context,
        vector_context=vector_context,
        graph_context=graph_context,
        web_context=web_context,
        use_reasoning=use_reasoning,
    )
    out = dict(result)
    out["answer"] = answer
    source_scope = dict(out.get("source_scope", {}) or {})
    source_scope["answer_resynthesized"] = True
    out["source_scope"] = source_scope
    return out


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
        except Exception:
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
    return guessed if guessed in {"general", "cybersecurity", "artificial_intelligence", "pdf_text", "policy"} else "general"


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
