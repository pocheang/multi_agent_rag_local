"""Lazy adapter for the legacy answer-synthesis entry point."""

from __future__ import annotations

from typing import Any


def synthesize_answer(*args: Any, **kwargs: Any) -> dict[str, Any]:
    """Delegate answer generation without exposing agent imports to API helpers."""
    from app.agents.synthesizer.generation import synthesize_answer as legacy_synthesize_answer

    return legacy_synthesize_answer(*args, **kwargs)
