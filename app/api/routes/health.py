"""Health check and metrics routes for the Multi-Agent Local RAG API."""
import os
import socket
import sys
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse, RedirectResponse, Response

from app.api.dependencies import query_guard, runtime_metrics, settings, shadow_queue
from app.api.middleware import get_request_metrics
from app.services.log_buffer import list_captured_logs
from app.services.model_config_store import get_global_model_settings, public_global_model_settings

router = APIRouter()


def _check_ollama_ready() -> dict[str, Any]:
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


def _check_neo4j_ready() -> dict[str, Any]:
    start = time.perf_counter()
    try:
        parsed = urlparse(settings.neo4j_uri or "")
        host = parsed.hostname or "localhost"
        port = int(parsed.port or 7687)
        with socket.create_connection((host, port), timeout=3):
            pass
        latency = int((time.perf_counter() - start) * 1000)
        return {"ok": True, "required": True, "latency_ms": latency}
    except Exception as e:
        latency = int((time.perf_counter() - start) * 1000)
        return {"ok": False, "required": True, "latency_ms": latency, "error": str(e)}


def _check_chroma_ready() -> dict[str, Any]:
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


def _runtime_diagnostics_summary() -> dict[str, Any]:
    conda_prefix = str(os.environ.get("CONDA_PREFIX", "") or "").strip()
    conda_env = str(os.environ.get("CONDA_DEFAULT_ENV", "") or "").strip()
    recent_errors = list_captured_logs(limit=20, level="ERROR")
    global_model_settings = public_global_model_settings(get_global_model_settings())
    recent_failures = []
    _request_metrics_lock, _request_metrics = get_request_metrics()
    with _request_metrics_lock:
        for row in reversed(list(_request_metrics)):
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
        "ollama_base_url": str(settings.ollama_base_url or ""),
        "ollama_chat_model": str(settings.ollama_chat_model or ""),
        "ollama_embed_model": str(settings.ollama_embed_model or ""),
        "global_model_settings": global_model_settings,
        "recent_errors": recent_errors[:5],
        "recent_failures": recent_failures,
    }


@router.get("/")
def home():
    return RedirectResponse(url="/app/")


@router.get("/health")
def health():
    return {"status": "ok"}


@router.get("/metrics")
def metrics():
    guard = query_guard.stats()
    runtime_metrics.set_gauge("query_guard_inflight", float(guard.get("inflight", 0) or 0))
    runtime_metrics.set_gauge("query_guard_waiting", float(guard.get("waiting", 0) or 0))
    qstats = shadow_queue.stats()
    runtime_metrics.set_gauge("shadow_queue_size", float(qstats.get("queue_size", 0) or 0))
    runtime_metrics.set_gauge("shadow_queue_workers", float(qstats.get("workers", 0) or 0))
    return Response(content=runtime_metrics.render_prometheus(), media_type="text/plain; version=0.0.4")


@router.get("/ready")
def ready():
    checks = {
        "api": {"ok": True, "required": True, "latency_ms": 0},
        "ollama": _check_ollama_ready(),
        "neo4j": _check_neo4j_ready(),
        "chroma": _check_chroma_ready(),
    }
    blocking_failures = [name for name, detail in checks.items() if detail.get("required") and not detail.get("ok")]
    status_text = "ok" if not blocking_failures else "degraded"
    code = 200 if status_text == "ok" else 503
    payload = {
        "status": status_text,
        "blocking_failures": blocking_failures,
        "services": checks,
        "query_runtime": {
            "guard": query_guard.stats(),
            "shadow_queue": shadow_queue.stats(),
        },
    }
    return JSONResponse(content=payload, status_code=code)
