"""Application-facing gateway for governed MCP tool calls."""

from __future__ import annotations

from app.domain.contracts import ToolResult
from app.mcp.contracts import ToolCall
from app.mcp.registry import ToolRegistry
from app.orchestration.request import RequestActor


class MCPGateway:
    """Keep callers on one authorization, approval, and audit path."""

    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    async def invoke(self, call: ToolCall, actor: RequestActor) -> ToolResult:
        """Delegate every tool invocation to the governed registry."""
        return await self._registry.invoke(call, actor)
