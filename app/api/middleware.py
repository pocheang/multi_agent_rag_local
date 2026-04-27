"""
Request middleware for the Multi-Agent Local RAG API.
"""
import time
import uuid
from datetime import datetime, timezone
from typing import Any
from collections import deque
import threading

from fastapi import Request

from app.services.runtime_metrics import RuntimeMetrics


# Global metrics storage
_request_metrics_lock = threading.Lock()
_request_metrics: deque[dict[str, Any]] = deque(maxlen=3000)
runtime_metrics = RuntimeMetrics()


async def request_timing_middleware(request: Request, call_next):
    """Middleware to track request timing and add security headers."""
    started = time.perf_counter()
    status_code = 500
    error_text = ""
    trace_id = request.headers.get("x-trace-id", "").strip() or uuid.uuid4().hex
    request.state.trace_id = trace_id
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Trace-Id"] = trace_id
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")
        return response
    except Exception as e:
        error_text = type(e).__name__
        raise
    finally:
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        metric = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "method": request.method,
            "path": request.url.path,
            "status_code": status_code,
            "duration_ms": elapsed_ms,
            "error": error_text,
        }
        with _request_metrics_lock:
            _request_metrics.append(metric)
        runtime_metrics.inc("http_requests_total")
        runtime_metrics.inc(f"http_status_{status_code}_total")
        runtime_metrics.observe("http_request_duration", elapsed_ms / 1000.0)


def get_request_metrics() -> list[dict[str, Any]]:
    """Get recent request metrics."""
    with _request_metrics_lock:
        return list(_request_metrics)
