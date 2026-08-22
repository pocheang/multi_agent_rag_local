"""Health check and metrics routes for the QueryMind API."""

import os
import socket
import sys
import time
from typing import Any
from urllib.parse import urlparse

import httpx
from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse, RedirectResponse, Response

from app.__version__ import __version__
from app.api import dependencies as api_dependencies
from app.api.dependencies import runtime_metrics
from app.api.deps.auth import require_admin
from app.api.transport.middleware import get_request_metrics
from app.services.models.config_store import get_global_model_settings, public_global_model_settings
from app.services.observability.log_buffer import list_captured_logs

router = APIRouter()


def _public_readiness_detail(detail: dict[str, Any]) -> dict[str, Any]:
    """Keep probe output useful without exposing internal topology or paths."""
    public = {key: detail[key] for key in ("ok", "required", "latency_ms", "status", "dimension") if key in detail}
    if detail.get("error"):
        public["error"] = "dependency check failed"
    return public


def _check_ollama_ready() -> dict[str, Any]:
    settings = api_dependencies.get_query_runtime().settings
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
    settings = api_dependencies.get_query_runtime().settings
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
    settings = api_dependencies.get_query_runtime().settings
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
        return {
            "ok": False,
            "required": True,
            "latency_ms": latency,
            "path": str(settings.chroma_path),
            "error": str(e),
        }


def _check_redis_ready() -> dict[str, Any]:
    """Check Redis connection (if Redis cache backend is enabled)."""
    settings = api_dependencies.get_query_runtime().settings
    start = time.perf_counter()
    cache_backend = str(getattr(settings, "retrieval_cache_backend", "auto") or "auto").lower()

    # Redis is only required if explicitly configured
    required = cache_backend == "redis"

    if cache_backend == "off" or cache_backend == "memory":
        return {"ok": True, "required": False, "latency_ms": 0, "status": "not_configured"}

    try:
        import redis

        parsed = urlparse(settings.redis_url or "redis://localhost:6379/0")
        host = parsed.hostname or "localhost"
        port = int(parsed.port or 6379)

        client = redis.Redis(host=host, port=port, socket_connect_timeout=3, socket_timeout=3)
        client.ping()
        latency = int((time.perf_counter() - start) * 1000)
        return {"ok": True, "required": required, "latency_ms": latency, "host": f"{host}:{port}"}
    except ImportError:
        latency = int((time.perf_counter() - start) * 1000)
        return {"ok": False, "required": required, "latency_ms": latency, "error": "redis package not installed"}
    except Exception as e:
        latency = int((time.perf_counter() - start) * 1000)
        return {"ok": False, "required": required, "latency_ms": latency, "error": str(e)}


def _check_postgres_ready() -> dict[str, Any]:
    """Check PostgreSQL database connection."""
    start = time.perf_counter()
    try:
        # Try to import database module
        try:
            from app.core.database import get_db_session
        except ImportError:
            # Database module not configured - this is OK for now
            return {"ok": True, "required": False, "latency_ms": 0, "status": "not_configured"}

        # Try to get a database session and execute a simple query
        with get_db_session() as session:
            session.execute("SELECT 1")

        latency = int((time.perf_counter() - start) * 1000)
        return {"ok": True, "required": False, "latency_ms": latency}
    except Exception as e:
        latency = int((time.perf_counter() - start) * 1000)
        # PostgreSQL is optional for now - don't fail readiness
        return {"ok": False, "required": False, "latency_ms": latency, "error": str(e)}


def _check_openai_api_ready() -> dict[str, Any]:
    """Check OpenAI API availability (if configured as backend)."""
    settings = api_dependencies.get_query_runtime().settings
    start = time.perf_counter()
    backend = str(settings.model_backend or "").lower()
    required = backend == "openai"

    if backend != "openai":
        return {"ok": True, "required": False, "latency_ms": 0, "status": "not_configured"}

    if not settings.openai_api_key:
        return {"ok": False, "required": True, "latency_ms": 0, "error": "OPENAI_API_KEY not configured"}

    try:
        base_url = (settings.openai_base_url or "https://api.openai.com/v1").rstrip("/")
        headers = {"Authorization": f"Bearer {settings.openai_api_key}"}

        with httpx.Client(timeout=5.0) as client:
            # Check models endpoint (lightweight check)
            resp = client.get(f"{base_url}/models", headers=headers)
            resp.raise_for_status()

        latency = int((time.perf_counter() - start) * 1000)
        return {"ok": True, "required": required, "latency_ms": latency, "base_url": base_url}
    except Exception as e:
        latency = int((time.perf_counter() - start) * 1000)
        return {"ok": False, "required": required, "latency_ms": latency, "error": str(e)}


def _check_anthropic_api_ready() -> dict[str, Any]:
    """Check Anthropic API availability (if configured as backend)."""
    settings = api_dependencies.get_query_runtime().settings
    start = time.perf_counter()
    backend = str(settings.model_backend or "").lower()
    required = backend == "anthropic"

    if backend != "anthropic":
        return {"ok": True, "required": False, "latency_ms": 0, "status": "not_configured"}

    if not settings.anthropic_api_key:
        return {"ok": False, "required": True, "latency_ms": 0, "error": "ANTHROPIC_API_KEY not configured"}

    try:
        # Simple connectivity check - just verify the key format
        if not settings.anthropic_api_key.startswith("sk-ant-"):
            return {"ok": False, "required": required, "latency_ms": 0, "error": "Invalid API key format"}

        latency = int((time.perf_counter() - start) * 1000)
        return {"ok": True, "required": required, "latency_ms": latency, "status": "key_configured"}
    except Exception as e:
        latency = int((time.perf_counter() - start) * 1000)
        return {"ok": False, "required": required, "latency_ms": latency, "error": str(e)}


def _check_embedding_model_ready() -> dict[str, Any]:
    """Check if embedding model is loaded and ready."""
    start = time.perf_counter()
    try:
        # Try to access the embedding model
        from app.retrievers.stores.vector import get_embeddings

        embeddings = get_embeddings()
        # Quick validation - embed a test string
        test_embedding = embeddings.embed_query("test")

        if not test_embedding or len(test_embedding) == 0:
            raise ValueError("Embedding returned empty result")

        latency = int((time.perf_counter() - start) * 1000)
        return {
            "ok": True,
            "required": True,
            "latency_ms": latency,
            "dimension": len(test_embedding),
        }
    except Exception as e:
        latency = int((time.perf_counter() - start) * 1000)
        return {"ok": False, "required": True, "latency_ms": latency, "error": str(e)}


def _runtime_diagnostics_summary() -> dict[str, Any]:
    settings = api_dependencies.get_query_runtime().settings
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
    """
    Basic liveness probe - returns OK if the API process is running.
    Use /ready for comprehensive dependency checks.
    """
    return {
        "status": "ok",
        "service": "querymind-api",
        "version": __version__,
    }


@router.get("/metrics")
def metrics():
    query_runtime = api_dependencies.get_query_runtime()
    guard = query_runtime.query_guard.stats()
    runtime_metrics.set_gauge("query_guard_inflight", float(guard.get("inflight", 0) or 0))
    runtime_metrics.set_gauge("query_guard_waiting", float(guard.get("waiting", 0) or 0))
    qstats = query_runtime.shadow_queue.stats()
    runtime_metrics.set_gauge("shadow_queue_size", float(qstats.get("queue_size", 0) or 0))
    runtime_metrics.set_gauge("shadow_queue_workers", float(qstats.get("workers", 0) or 0))
    return Response(content=runtime_metrics.render_prometheus(), media_type="text/plain; version=0.0.4")


@router.get("/ready")
def ready():
    """
    Readiness probe - comprehensive check of all dependencies.
    Returns 200 if all required services are healthy, 503 if any required service fails.
    """
    checks = {
        "api": {"ok": True, "required": True, "latency_ms": 0},
        "postgres": _check_postgres_ready(),
        "redis": _check_redis_ready(),
        "ollama": _check_ollama_ready(),
        "openai": _check_openai_api_ready(),
        "anthropic": _check_anthropic_api_ready(),
        "neo4j": _check_neo4j_ready(),
        "chroma": _check_chroma_ready(),
        "embedding_model": _check_embedding_model_ready(),
    }

    # Identify blocking failures (required services that are not OK)
    blocking_failures = [name for name, detail in checks.items() if detail.get("required") and not detail.get("ok")]

    # Determine overall status
    if not blocking_failures:
        status_text = "healthy"
        code = 200
    elif len(blocking_failures) < len([s for s in checks.values() if s.get("required")]):
        status_text = "degraded"
        code = 200  # Partially healthy - can still serve requests
    else:
        status_text = "unhealthy"
        code = 503

    query_runtime = api_dependencies.get_query_runtime()
    payload = {
        "status": status_text,
        "blocking_failures": blocking_failures,
        "services": {name: _public_readiness_detail(detail) for name, detail in checks.items()},
        "query_runtime": {
            "guard": query_runtime.query_guard.stats(),
            "shadow_queue": query_runtime.shadow_queue.stats(),
        },
        "timestamp": time.time(),
    }
    return JSONResponse(content=payload, status_code=code)


@router.get("/circuit-breakers", dependencies=[Depends(require_admin)])
def circuit_breaker_status():
    """
    Get status of all circuit breakers in the system.

    Returns the state, failure count, and opened time for each circuit.
    Use this to monitor resilience mechanisms and identify failing services.
    """
    from app.services.runtime.resilience import _BREAKERS, _BREAKERS_LOCK

    circuits = {}
    current_time = time.time()

    with _BREAKERS_LOCK:
        for name, state in _BREAKERS.items():
            is_open = state.opened_until > current_time
            circuits[name] = {
                "state": "open" if is_open else "closed",
                "consecutive_failures": state.fails,
                "opened_until": state.opened_until if is_open else None,
                "time_until_retry": max(0, int(state.opened_until - current_time)) if is_open else 0,
            }

    return {
        "timestamp": current_time,
        "total_circuits": len(circuits),
        "open_circuits": sum(1 for c in circuits.values() if c["state"] == "open"),
        "circuits": circuits,
    }
