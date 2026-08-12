"""Transport-neutral helpers for typed Engine stream events."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def terminal_contract(event: Mapping[str, Any]) -> dict[str, Any]:
    """Return only the terminal fields promised by the typed SSE contract."""
    result = event.get("result") if event.get("type") == "done" else None
    if not isinstance(result, Mapping):
        return {}
    return {
        "answer": result.get("answer", ""),
        "citations": list(result.get("citations", []) or []),
        "route": result.get("route", "unknown"),
        "validation_status": result.get("validation_status", "degraded"),
        "grounding": dict(result.get("grounding", {}) or {}),
        "safety": dict(result.get("safety", {}) or {}),
        "execution_metadata": dict(result.get("execution_metadata", {}) or {}),
    }


__all__ = ["terminal_contract"]
