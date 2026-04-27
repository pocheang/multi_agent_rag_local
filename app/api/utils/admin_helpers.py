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
