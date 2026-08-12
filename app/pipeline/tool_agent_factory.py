"""Compatibility exports for the canonical tool-agent factory."""

from app.agents.tool.factory import ToolAgent, create_tool_agent, get_disable_connector_tool_id

__all__ = ["ToolAgent", "create_tool_agent", "get_disable_connector_tool_id"]
