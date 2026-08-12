"""Audit coverage for governed MCP decisions."""

import pytest

from app.domain.contracts import ToolResult
from app.mcp.approvals import ApprovalStore
from app.mcp.audit import AuditLog
from app.mcp.authorization import AuthorizationPolicy
from app.mcp.contracts import ToolArgument, ToolCall, ToolDefinition
from app.mcp.registry import ToolRegistry
from app.orchestration.request import RequestActor


@pytest.mark.asyncio
async def test_audit_records_approval_actor_and_argument_names_without_argument_values() -> None:
    """Auditing a write call must preserve accountability without persisting secret text."""
    async def write_note(call: ToolCall, actor: RequestActor) -> ToolResult:
        del actor
        return ToolResult(tool_id=call.tool_id, status="succeeded", summary="note created")

    approvals = ApprovalStore()
    audit = AuditLog()
    registry = ToolRegistry(authorization=AuthorizationPolicy(), approvals=approvals, audit=audit)
    registry.register(
        ToolDefinition(
            tool_id="querymind_crm_write_note",
            connector_id="crm",
            operation="write",
            required_scopes=frozenset({"connector:write"}),
        ),
        write_note,
    )
    actor = RequestActor(user_id="user-1", permissions=frozenset({"connector:write"}))
    call = ToolCall(
        tool_id="querymind_crm_write_note",
        arguments=(ToolArgument(name="note", value="private customer note"),),
        execution_id="execution-1",
    )

    pending = await registry.invoke(call, actor)
    assert audit.records[-1].connector_id == "crm"
    approvals.approve(pending.approval_token, actor)
    await registry.invoke(call.model_copy(update={"approval_token": pending.approval_token}), actor)

    approved_record = audit.records[-1]
    assert approved_record.actor_id == "user-1"
    assert approved_record.connector_id == "crm"
    assert approved_record.argument_names == ("note",)
    assert approved_record.approved_by == "user-1"
    assert approved_record.execution_id == "execution-1"
    assert "private customer note" not in approved_record.summary

@pytest.mark.asyncio
async def test_audit_never_persists_a_connector_result_body() -> None:
    """A connector-provided summary may contain secrets and must not reach the audit log."""
    async def read_secret(call: ToolCall, actor: RequestActor) -> ToolResult:
        del actor
        return ToolResult(tool_id=call.tool_id, status="succeeded", summary="Bearer private-token")

    audit = AuditLog()
    registry = ToolRegistry(authorization=AuthorizationPolicy(), approvals=ApprovalStore(), audit=audit)
    registry.register(
        ToolDefinition(tool_id="querymind_crm_read_secret", connector_id="crm", operation="read"),
        read_secret,
    )

    await registry.invoke(
        ToolCall(tool_id="querymind_crm_read_secret"),
        RequestActor(user_id="user-1"),
    )

    assert audit.records[-1].summary == "tool result: succeeded"
    assert "private-token" not in audit.records[-1].summary
