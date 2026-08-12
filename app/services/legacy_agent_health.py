"""Lazy adapters for legacy agent health validation used by HTTP routes."""

from __future__ import annotations

from typing import Any

_HEALTH_CHECKS = {
    "router": "validate_router_agent",
    "vector_rag": "validate_vector_rag_agent",
    "graph_rag": "validate_graph_rag_agent",
    "react": "validate_react_agent",
    "synthesis": "validate_synthesis_agent",
    "enhanced_router": "validate_enhanced_router_agent",
    "workflow": "validate_workflow",
}


def validate_all_agents() -> dict[str, Any]:
    """Delegate the complete legacy agent validation report."""
    from app.services.observability.agent_health import AgentValidator

    return AgentValidator.validate_all()


def available_agent_health_checks() -> tuple[str, ...]:
    """Return the stable HTTP names accepted by the legacy validator."""
    return tuple(_HEALTH_CHECKS)


def validate_agent(agent_name: str) -> dict[str, Any]:
    """Delegate one named legacy agent health validation.

    Raises:
        KeyError: If the requested HTTP agent name has no legacy validator.
    """
    from app.services.observability.agent_health import AgentValidator

    method_name = _HEALTH_CHECKS[agent_name]
    return getattr(AgentValidator, method_name)()


def get_agent_config_values() -> dict[str, Any]:
    """Load the legacy agent configuration values exposed by the API."""
    from app.agents.agent_config import (
        CHUNK_PREVIEW_LENGTH,
        DENSE_SCORE_THRESHOLD,
        VALID_AGENT_CLASSES,
        VALID_ROUTES,
        VALID_SKILLS,
    )

    return {
        "chunk_preview_length": CHUNK_PREVIEW_LENGTH,
        "dense_score_threshold": DENSE_SCORE_THRESHOLD,
        "valid_agent_classes": VALID_AGENT_CLASSES,
        "valid_routes": VALID_ROUTES,
        "valid_skills": VALID_SKILLS,
    }
