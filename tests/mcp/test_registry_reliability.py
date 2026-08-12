"""Reliability boundaries for governed MCP tool invocation."""

import asyncio

import pytest

from app.domain.contracts import ToolResult
from app.mcp.approvals import ApprovalStore
from app.mcp.authorization import AuthorizationPolicy
from app.mcp.contracts import ToolCall, ToolDefinition
from app.mcp.registry import ToolRegistry
from app.orchestration.request import RequestActor


@pytest.mark.asyncio
async def test_registry_times_out_external_tool_at_registered_limit() -> None:
    """A declared tool timeout must prevent an indefinitely running connector."""
    async def slow_tool(call: ToolCall, actor: RequestActor) -> ToolResult:
        del call, actor
        await asyncio.sleep(1.1)
        return ToolResult(tool_id="querymind_connector_read_slow", status="succeeded")

    registry = ToolRegistry(authorization=AuthorizationPolicy(), approvals=ApprovalStore())
    registry.register(
        ToolDefinition(
            tool_id="querymind_connector_read_slow",
            operation="read",
            timeout_seconds=1,
        ),
        slow_tool,
    )

    result = await registry.invoke(
        ToolCall(tool_id="querymind_connector_read_slow"),
        RequestActor(user_id="user-1"),
    )

    assert result.status == "failed"
    assert result.summary == "tool timed out"

@pytest.mark.asyncio
async def test_registry_rejects_an_executor_result_for_another_tool() -> None:
    """Connector output must remain correlated to the tool call that produced it."""
    async def mismatched_tool(call: ToolCall, actor: RequestActor) -> ToolResult:
        del call, actor
        return ToolResult(tool_id="querymind_other_read_data", status="succeeded")

    registry = ToolRegistry(authorization=AuthorizationPolicy(), approvals=ApprovalStore())
    registry.register(
        ToolDefinition(tool_id="querymind_connector_read_records", operation="read"),
        mismatched_tool,
    )

    result = await registry.invoke(
        ToolCall(tool_id="querymind_connector_read_records"),
        RequestActor(user_id="user-1"),
    )

    assert result.tool_id == "querymind_connector_read_records"
    assert result.status == "failed"
    assert result.summary == "tool returned an unexpected tool id"
