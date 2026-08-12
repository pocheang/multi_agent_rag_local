"""Compatibility re-export for app.agents.router.validator; implementation lives in the canonical package."""

from app.agents.router.validator import (
    record_route_outcome,
    validate_route_decision,
)

__all__ = [
    "validate_route_decision",
    "record_route_outcome",
]
