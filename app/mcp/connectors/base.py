"""Typed connector execution boundary."""

from __future__ import annotations

from typing import Protocol

from app.domain.contracts import ToolResult
from app.mcp.contracts import ToolCall
from app.orchestration.request import RequestActor


class Connector(Protocol):
    """A connector executes only one already-governed tool call."""

    async def invoke(self, call: ToolCall, actor: RequestActor) -> ToolResult:
        """Return a user-displayable result without leaking credentials."""
