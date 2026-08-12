"""Typed adapter from explicit RAG tool requests to the governed MCP gateway."""

from __future__ import annotations

import re
from uuid import uuid4

from app.domain.contracts import EvidenceBundle, RouteDecision, TaskPlan, ToolResult
from app.mcp.contracts import ToolArgument, ToolCall
from app.mcp.gateway import MCPGateway
from app.orchestration.request import OrchestrationRequest
from app.services.connectors.management import ConnectorManagementService

DISABLE_CONNECTOR_TOOL_ID = "querymind_connector_disable_owned"
_DISABLE_CONNECTOR = re.compile(
    r"^\s*(?:please\s+)?disable\s+(?:the\s+)?(?:connector|integration)\s+"
    r"(?P<connector_id>[a-z][a-z0-9_-]{0,63})\s*[.!]?\s*$",
    re.IGNORECASE,
)


class ToolAgentService:
    """Recognize bounded user tool intent and invoke only registered governed tools."""

    def __init__(
        self,
        gateway: MCPGateway | None = None,
        connectors: ConnectorManagementService | None = None,
    ) -> None:
        self._gateway = gateway
        self._connectors = connectors

    async def invoke_requested(
        self,
        request: OrchestrationRequest,
        *,
        execution_id: str,
    ) -> tuple[ToolResult, ...]:
        """Invoke an explicit owned-connector command, or leave ordinary RAG queries untouched."""
        call = self._disable_connector_call(request.question, execution_id)
        actor = request.actor
        if call is None or actor is None or not actor.user_id or self._gateway is None or self._connectors is None:
            return ()
        connector_id = call.arguments[0].value
        owned = next(
            (item for item in self._connectors.list_for_owner(actor.user_id) if item.connector_id == connector_id),
            None,
        )
        if owned is None or owned.status != "enabled":
            return (
                ToolResult(
                    tool_id=call.tool_id,
                    status="failed",
                    summary="owned enabled connector not found",
                ),
            )
        return (await self._gateway.invoke(call, actor),)

    async def run(
        self,
        request: OrchestrationRequest,
        route: RouteDecision,
        plan: TaskPlan,
        evidence: EvidenceBundle,
    ) -> tuple[ToolResult, ...]:
        """Use the same governed boundary when called by the typed orchestration engine."""
        del route, plan, evidence
        return await self.invoke_requested(request, execution_id=request.execution_id or request.request_id or str(uuid4()))

    @staticmethod
    def _disable_connector_call(question: str, execution_id: str) -> ToolCall | None:
        command = question.partition("\n")[0]
        match = _DISABLE_CONNECTOR.fullmatch(command)
        if match is None:
            return None
        return ToolCall(
            tool_id=DISABLE_CONNECTOR_TOOL_ID,
            arguments=(ToolArgument(name="connector_id", value=match.group("connector_id").lower()),),
            execution_id=execution_id,
        )
