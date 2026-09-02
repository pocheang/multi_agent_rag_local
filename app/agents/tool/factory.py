"""Canonical construction boundary for the governed tool agent."""

from __future__ import annotations

from typing import Any, Protocol

__all__ = ["ToolAgent", "create_tool_agent"]


class ToolAgent(Protocol):
    """Minimum tool-agent capability consumed by the application runtime."""

    async def invoke_requested(self, request: Any, *, execution_id: str) -> tuple[Any, ...]:
        """Invoke a bounded, explicitly requested tool operation."""


def create_tool_agent(gateway: Any, registry: Any) -> ToolAgent:
    """Construct the governed tool agent around application-owned dependencies.

    Takes the registry, not the connector service: the agent no longer
    pre-checks connector ownership itself (the registered executor owns that
    check), but it does need the registry's catalogue to tell a selector which
    tools this actor may use.
    """
    from app.agents.tool.service import ToolAgentService

    return ToolAgentService(gateway, registry)
