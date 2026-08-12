"""Scope checks for governed MCP tools."""

from __future__ import annotations

from app.mcp.contracts import ToolDefinition
from app.orchestration.request import RequestActor


class AuthorizationPolicy:
    """Authorize a tool only when every declared scope is held by the actor."""

    def allows(self, definition: ToolDefinition, actor: RequestActor) -> bool:
        return bool(actor.user_id) and definition.required_scopes.issubset(actor.permissions)
