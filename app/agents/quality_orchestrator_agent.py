"""Compatibility re-export for app.agents.validation.quality_orchestrator; implementation lives in the canonical package."""

from app.agents.validation.quality_orchestrator import (
    orchestrate_quality,
)

__all__ = [
    "orchestrate_quality",
]
