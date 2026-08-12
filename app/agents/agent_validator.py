"""Compatibility entry point for :mod:`app.services.agent_health_validator`."""

from app.services.agent_health_validator import AgentValidator, main, validate_agent_integration

__all__ = ["AgentValidator", "validate_agent_integration"]


if __name__ == "__main__":
    main()
