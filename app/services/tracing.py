from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from app.core.config import get_settings


@contextmanager
def traced_span(name: str, attributes: dict[str, Any] | None = None) -> Iterator[None]:
    settings = get_settings()
    if not bool(getattr(settings, "otel_tracing_enabled", True)):
        yield
        return
    try:
        from opentelemetry import trace
    except ImportError:
        yield
        return
    tracer = trace.get_tracer("querymind")
    with tracer.start_as_current_span(name) as span:
        for k, v in (attributes or {}).items():
            try:
                span.set_attribute(k, v)
            except (ValueError, TypeError):
                continue
        yield
