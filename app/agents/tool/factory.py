"""Canonical construction boundary for the governed tool agent."""

from __future__ import annotations

from typing import Any, Protocol

__all__ = ["ToolAgent", "create_tool_agent", "get_disable_connector_tool_id"]


class ToolAgent(Protocol):
    """Minimum tool-agent capability consumed by the application runtime."""

    async def invoke_requested(self, request: Any, *, execution_id: str) -> tuple[Any, ...]:
        """Invoke a bounded, explicitly requested tool operation."""


def get_disable_connector_tool_id() -> str:
    """Return the legacy connector-disable tool identifier."""
    from app.agents.tool.service import DISABLE_CONNECTOR_TOOL_ID

    return DISABLE_CONNECTOR_TOOL_ID


def create_tool_agent(gateway: Any, connectors: Any) -> ToolAgent:
    """Construct the governed tool agent around application-owned dependencies."""
    from app.agents.tool.service import ToolAgentService

    return ToolAgentService(gateway, connectors)
