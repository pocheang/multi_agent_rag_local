"""Non-invasive availability checks for legacy agent-health endpoints.

The health API reports whether the optional execution components are present.
It deliberately does not construct agents, execute retrieval/generation, or
build a workflow: those operations belong to the request pipeline, not an
observability endpoint.
"""

from __future__ import annotations

import importlib.util
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _module_status(component: str, module_name: str) -> dict[str, Any]:
    """Return a lightweight health report without importing the component."""
    try:
        available = importlib.util.find_spec(module_name) is not None
    except (ImportError, ModuleNotFoundError, ValueError) as exc:
        logger.warning("Unable to inspect %s health: %s", component, exc)
        available = False

    if available:
        return {
            "status": "ok",
            "agent": component,
            "check": "module_available",
            "module": module_name,
        }

    return {
        "status": "error",
        "agent": component,
        "check": "module_available",
        "module": module_name,
        "error": "Component module is unavailable",
    }


class AgentValidator:
    """Validate component availability without running Agent workloads."""

    @staticmethod
    def validate_router_agent() -> dict[str, Any]:
        """Validate Router Agent module availability."""
        return _module_status("router", "app.agents.router.routing")

    @staticmethod
    def validate_vector_rag_agent() -> dict[str, Any]:
        """Validate Vector RAG Agent module availability."""
        return _module_status("vector_rag", "app.agents.rag.vector")

    @staticmethod
    def validate_graph_rag_agent() -> dict[str, Any]:
        """Validate Graph RAG Agent module availability."""
        return _module_status("graph_rag", "app.agents.rag.graph")

    @staticmethod
    def validate_synthesis_agent() -> dict[str, Any]:
        """Validate synthesis Agent module availability."""
        return _module_status("synthesis", "app.agents.synthesizer.generation")

    @staticmethod
    def validate_enhanced_router_agent() -> dict[str, Any]:
        """Validate Enhanced Router Agent module availability."""
        return _module_status("enhanced_router", "app.agents.enhanced_router_agent")

    @staticmethod
    def validate_workflow() -> dict[str, Any]:
        """Validate the workflow module is available without constructing it."""
        result = _module_status("workflow", "app.graph.execution.workflow")
        result["component"] = result.pop("agent")
        return result

    @classmethod
    def validate_all(cls) -> dict[str, Any]:
        """Run all non-invasive component availability checks."""
        results = {
            "router": cls.validate_router_agent(),
            "vector_rag": cls.validate_vector_rag_agent(),
            "graph_rag": cls.validate_graph_rag_agent(),
            "synthesis": cls.validate_synthesis_agent(),
            "enhanced_router": cls.validate_enhanced_router_agent(),
            "workflow": cls.validate_workflow(),
        }

        statuses = [result.get("status") for result in results.values()]
        error_count = statuses.count("error")
        fallback_count = statuses.count("fallback")
        ok_count = statuses.count("ok")

        overall_status = "healthy"
        if error_count > 0:
            overall_status = "degraded" if ok_count > error_count else "unhealthy"
        elif fallback_count > 0:
            overall_status = "partially_healthy"

        return {
            "overall_status": overall_status,
            "summary": {
                "total": len(results),
                "ok": ok_count,
                "fallback": fallback_count,
                "error": error_count,
            },
            "details": results,
        }


def validate_agent_integration() -> dict[str, Any]:
    """Return the complete legacy-compatible health report."""
    return AgentValidator.validate_all()


def main() -> None:
    """Run the health validator as a command-line entry point."""
    import json

    logging.basicConfig(level=logging.INFO)
    print(json.dumps(validate_agent_integration(), indent=2, ensure_ascii=False))


__all__ = ["AgentValidator", "main", "validate_agent_integration"]
