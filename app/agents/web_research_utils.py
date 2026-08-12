"""Compatibility re-export for app.agents.rag.web_utils; implementation lives in the canonical package."""

from app.agents.rag.web_utils import (
    WebSearchMetrics,
    get_metrics,
    is_time_sensitive_query,
    reset_metrics,
    run_parallel_web_research,
    validate_url,
)

__all__ = [
    "validate_url",
    "run_parallel_web_research",
    "is_time_sensitive_query",
    "WebSearchMetrics",
    "get_metrics",
    "reset_metrics",
]
