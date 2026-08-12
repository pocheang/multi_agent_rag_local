"""Compatibility entry point for :mod:`app.services.observability.agent_health`."""

from app.services.observability.agent_health import (
    AgentValidator,
    main,
    validate_agent_integration,
)

__all__ = ["AgentValidator", "main", "validate_agent_integration"]


if __name__ == "__main__":
    main()
