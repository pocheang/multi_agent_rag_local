"""Compatibility re-export for app.agents.shared.base; implementation lives in the canonical package."""

from app.agents.shared.base import (
    AgentError,
    AgentTimeoutError,
    AgentValidationError,
    BaseAgent,
)

__all__ = [
    "AgentError",
    "AgentTimeoutError",
    "AgentValidationError",
    "BaseAgent",
]
