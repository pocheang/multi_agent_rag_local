"""
Admin-related helper functions for the Multi-Agent Local RAG API.
"""
import os
import re
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.log_buffer import list_captured_logs
from app.services.model_config_store import get_global_model_settings, public_global_model_settings

settings = get_settings()


def _parse_audit_ts(value: str | None) -> datetime:
    """Parse an audit timestamp."""
    if not value:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    try:
        dt = datetime.fromisoformat(value)
    except Exception:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _filter_audit_rows(
    rows: list[dict[str, Any]],
    cutoff: datetime,
    actor_user_id: str | None = None,
    action_keyword: str | None = None,
) -> list[dict[str, Any]]:
    """Filter audit rows by criteria."""
    filtered: list[dict[str, Any]] = []
    actor_filter = (actor_user_id or "").strip()
    action_filter = (action_keyword or "").strip().lower()
    for row in rows:
        if _parse_audit_ts(str(row.get("created_at", ""))) < cutoff:
            continue
        if actor_filter and str(row.get("actor_user_id", "") or "") != actor_filter:
            continue
        if action_filter and action_filter not in str(row.get("action", "")).lower():
            continue
        filtered.append(row)
    return filtered


def _parse_request_ts(value: str | None) -> datetime:
    """Parse a request timestamp."""
    if not value:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    try:
        dt = datetime.fromisoformat(value)
    except Exception:
        return datetime.fromtimestamp(0, tz=timezone.utc)
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _extract_grounding_support_from_detail(detail: str | None) -> float | None:
    """Extract grounding support score from detail string."""
    text = str(detail or "")
    m = re.search(r"grounding_support=([0-9]*\.?[0-9]+)", text)
    if not m:
        return None
    try:
        v = float(m.group(1))
    except Exception:
        return None
    if v < 0:
        return 0.0
    if v > 1:
        return 1.0
    return v


def _load_benchmark_queries(path: Path, limit: int = 100) -> list[str]:
    """Load benchmark queries from a file."""
    if not path.exists():
        return []
    rows: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        q = line.strip()
        if q:
            rows.append(q)
    return rows[: max(1, limit)]


def _check_ollama_ready() -> dict[str, Any]:
    """Check if Ollama service is ready."""
    start = time.perf_counter()
    url = (settings.ollama_base_url or "http://localhost:11434").rstrip("/") + "/api/tags"
    try:
        with httpx.Client(timeout=3.0) as client:
            resp = client.get(url)
            resp.raise_for_status()
            payload = resp.json()
        models = [str(x.get("name", "") or "") for x in list((payload or {}).get("models", []) or []) if x]
        latency = int((time.perf_counter() - start) * 1000)
        return {
            "ok": True,
            "required": settings.model_backend.lower() == "ollama",
            "latency_ms": latency,
            "path": url,
            "models": models[:8],
        }
    except Exception as e:
        latency = int((time.perf_counter() - start) * 1000)
        return {
            "ok": False,
            "required": settings.model_backend.lower() == "ollama",
            "latency_ms": latency,
            "path": url,
            "error": str(e),
        }


def _check_chroma_ready() -> dict[str, Any]:
    """Check if ChromaDB storage is ready."""
    start = time.perf_counter()
    try:
        settings.chroma_path.mkdir(parents=True, exist_ok=True)
        probe = settings.chroma_path / ".ready_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink(missing_ok=True)
        latency = int((time.perf_counter() - start) * 1000)
        return {"ok": True, "required": True, "latency_ms": latency, "path": str(settings.chroma_path)}
    except Exception as e:
        latency = int((time.perf_counter() - start) * 1000)
        return {"ok": False, "required": True, "latency_ms": latency, "path": str(settings.chroma_path), "error": str(e)}


def _runtime_diagnostics_summary(get_request_metrics_fn) -> dict[str, Any]:
    """Get runtime diagnostics summary."""
    conda_prefix = str(os.environ.get("CONDA_PREFIX", "") or "").strip()
    conda_env = str(os.environ.get("CONDA_DEFAULT_ENV", "") or "").strip()
    recent_errors = list_captured_logs(limit=20, level="ERROR")
    global_model_settings = public_global_model_settings(get_global_model_settings())
    recent_failures = []

    for row in reversed(get_request_metrics_fn()):
        status_code = int(row.get("status_code", 0) or 0)
        error = str(row.get("error", "") or "")
        if status_code < 400 and not error:
            continue
        recent_failures.append(
            {
                "ts": str(row.get("ts", "")),
                "path": str(row.get("path", "")),
                "status_code": status_code,
                "error": error,
                "duration_ms": int(row.get("duration_ms", 0) or 0),
            }
        )
        if len(recent_failures) >= 10:
            break

    return {
        "python_executable": sys.executable,
        "python_version": sys.version.split()[0],
        "conda_prefix": conda_prefix,
        "conda_env": conda_env,
        "model_backend": str(settings.model_backend or ""),
        "reasoning_model_backend": str(settings.reasoning_model_backend or settings.model_backend or ""),
        "global_model_settings": global_model_settings,
        "recent_errors": recent_errors,
        "recent_failures": recent_failures,
    }


# Security-related helper functions for admin operations

def validate_and_check_approval_token(
    approval_token: str,
    actor_user_id: str,
    audit_callback: callable,
    request: Any,
    user: dict[str, Any],
    action: str
) -> tuple[bool, str]:
    """
    Validate approval token and handle errors (prevent information disclosure).

    Args:
        approval_token: Approval token to validate
        actor_user_id: User ID performing the operation
        audit_callback: Audit log callback function
        request: FastAPI request object
        user: User information
        action: Operation type

    Returns:
        (token_ok, token_mode) tuple

    Raises:
        HTTPException: If token is invalid or configuration is missing
    """
    from fastapi import HTTPException
    from app.services.admin_token_tracker import validate_admin_approval_token, get_token_tracker

    configured_hash = str(
        getattr(settings, "admin_create_approval_token_hash", "") or ""
    ).strip().lower()

    tracker = get_token_tracker()
    token_ok, token_mode = validate_admin_approval_token(
        approval_token,
        configured_hash,
        actor_user_id,
        tracker
    )

    # Unified error handling, no configuration information leakage
    if not token_ok:
        audit_callback(
            request,
            action=action,
            resource_type="user",
            result="failed",
            user=user,
            detail=f"approval_failed; mode={token_mode}"
        )
        raise HTTPException(status_code=403, detail="unauthorized")

    return token_ok, token_mode


def handle_service_exception(
    e: Exception,
    audit_callback: callable,
    request: Any,
    action: str,
    user: dict[str, Any],
    resource_id: str | None = None
) -> None:
    """
    Unified service layer exception handling with audit logging.

    Args:
        e: Exception object
        audit_callback: Audit log callback function
        request: FastAPI request object
        action: Operation type
        user: User information
        resource_id: Resource ID

    Raises:
        HTTPException: Converted HTTP exception
    """
    import logging
    from fastapi import HTTPException

    logger = logging.getLogger(__name__)

    audit_callback(
        request,
        action=action,
        resource_type="user",
        result="failed",
        user=user,
        resource_id=resource_id,
        detail=f"{type(e).__name__}: {str(e)}"
    )

    if isinstance(e, ValueError):
        raise HTTPException(status_code=400, detail=str(e))

    logger.error(f"Unexpected error in {action}: {e}", exc_info=True)
    raise HTTPException(status_code=500, detail="operation failed")

