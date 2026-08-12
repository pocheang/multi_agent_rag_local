"""TDD contract tests for governed MCP write calls."""

import pytest

from app.domain.contracts import ToolResult
from app.mcp.approvals import ApprovalStore
from app.mcp.authorization import AuthorizationPolicy
from app.mcp.contracts import ToolArgument, ToolCall, ToolDefinition
from app.mcp.registry import ToolRegistry
from app.orchestration.request import RequestActor


@pytest.mark.asyncio
async def test_unapproved_write_call_returns_approval_required_without_running_connector() -> None:
    """Removing the approval guard must never allow a write executor to run."""
    executed = False

    async def write_note(call: ToolCall, actor: RequestActor) -> ToolResult:
        nonlocal executed
        executed = True
        assert call.tool_id == "querymind_connector_write_note"
        assert actor.user_id == "user-1"
        return ToolResult(tool_id=call.tool_id, status="succeeded", summary="note created")

    approvals = ApprovalStore()
    registry = ToolRegistry(authorization=AuthorizationPolicy(), approvals=approvals)
    registry.register(
        ToolDefinition(
            tool_id="querymind_connector_write_note",
            operation="write",
            required_scopes=frozenset({"connector:write"}),
        ),
        write_note,
    )
    actor = RequestActor(user_id="user-1", permissions=frozenset({"connector:write"}))
    call = ToolCall(tool_id="querymind_connector_write_note")

    pending = await registry.invoke(call, actor)

    assert pending.status == "approval_required"
    assert pending.approval_status == "pending"
    assert pending.approval_token
    assert executed is False

    approvals.approve(pending.approval_token, actor)
    approved = await registry.invoke(call.model_copy(update={"approval_token": pending.approval_token}), actor)

    assert approved.status == "succeeded"
    assert approved.approval_status == "approved"
    assert executed is True

@pytest.mark.asyncio
async def test_approved_token_cannot_be_reused_with_different_arguments() -> None:
    """A confirmation for one write payload must not authorize a changed payload."""
    executed = False

    async def write_note(call: ToolCall, actor: RequestActor) -> ToolResult:
        nonlocal executed
        del call, actor
        executed = True
        return ToolResult(tool_id="querymind_connector_write_note", status="succeeded")

    approvals = ApprovalStore()
    registry = ToolRegistry(authorization=AuthorizationPolicy(), approvals=approvals)
    registry.register(
        ToolDefinition(
            tool_id="querymind_connector_write_note",
            operation="write",
            required_scopes=frozenset({"connector:write"}),
        ),
        write_note,
    )
    actor = RequestActor(user_id="user-1", permissions=frozenset({"connector:write"}))
    original = ToolCall(
        tool_id="querymind_connector_write_note",
        arguments=(ToolArgument(name="note", value="approved content"),),
    )

    pending = await registry.invoke(original, actor)
    approvals.approve(pending.approval_token, actor)
    changed = original.model_copy(
        update={
            "arguments": (ToolArgument(name="note", value="changed after approval"),),
            "approval_token": pending.approval_token,
        }
    )
    result = await registry.invoke(changed, actor)

    assert result.status == "approval_required"
    assert executed is False
