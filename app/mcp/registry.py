"""Governed tool registration and invocation."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from time import perf_counter

from app.domain.contracts import ToolResult
from app.domain.events import EventMetadata, ExecutionEvent
from app.mcp.approvals import ApprovalStore
from app.mcp.audit import AuditLog
from app.mcp.authorization import AuthorizationPolicy
from app.mcp.contracts import AuditRecord, ToolCall, ToolDefinition
from app.orchestration.execution_events import ExecutionEventStore
from app.orchestration.request import RequestActor

ToolExecutor = Callable[[ToolCall, RequestActor], Awaitable[ToolResult]]
_APPROVAL_OPERATIONS = frozenset({"write", "delete", "send", "charge"})


class ToolRegistry:
    """Invoke tools only after authorization, approval, and auditable policy checks."""

    def __init__(
        self,
        *,
        authorization: AuthorizationPolicy,
        approvals: ApprovalStore,
        audit: AuditLog | None = None,
        execution_events: ExecutionEventStore | None = None,
    ) -> None:
        self._authorization = authorization
        self._approvals = approvals
        self._audit = audit or AuditLog()
        self._execution_events = execution_events
        self._tools: dict[str, tuple[ToolDefinition, ToolExecutor]] = {}

    def register(self, definition: ToolDefinition, executor: ToolExecutor) -> None:
        """Register one unique, schema-governed tool implementation."""
        if definition.tool_id in self._tools:
            raise ValueError(f"tool already registered: {definition.tool_id}")
        self._tools[definition.tool_id] = (definition, executor)

    async def invoke(self, call: ToolCall, actor: RequestActor) -> ToolResult:
        """Evaluate all policy gates before the connector executor can run."""
        registered = self._tools.get(call.tool_id)
        if registered is None:
            return await self._finish(
                call, actor, ToolResult(tool_id=call.tool_id, status="failed", summary="unknown tool")
            )
        definition, executor = registered
        if not self._authorization.allows(definition, actor):
            return await self._finish(
                call,
                actor,
                ToolResult(tool_id=call.tool_id, status="failed", summary="scope denied"),
                definition=definition,
            )
        approval = self._approvals.consume(call, actor) if definition.operation in _APPROVAL_OPERATIONS else None
        if definition.operation in _APPROVAL_OPERATIONS and approval is None:
            pending_approval = self._approvals.create(call, actor)
            result = await self._finish(
                call,
                actor,
                ToolResult(
                    tool_id=call.tool_id,
                    status="approval_required",
                    approval_status="pending",
                    approval_token=pending_approval.token,
                    summary="approval required before this high-risk operation can run",
                ),
                definition=definition,
            )
            if self._execution_events is not None:
                self._execution_events.publish(
                    call.execution_id,
                    ExecutionEvent(
                        stage="tool",
                        status="skipped",
                        message="approval required",
                        metadata=(EventMetadata(key="approval_request_id", value=pending_approval.token),),
                    ),
                )
            return result
        started = perf_counter()
        try:
            result = await asyncio.wait_for(executor(call, actor), timeout=definition.timeout_seconds)
        except TimeoutError:
            result = ToolResult(tool_id=call.tool_id, status="failed", summary="tool timed out")
        except Exception as exc:
            result = ToolResult(tool_id=call.tool_id, status="failed", summary=f"tool failed: {type(exc).__name__}")
        if result.tool_id != call.tool_id:
            result = ToolResult(tool_id=call.tool_id, status="failed", summary="tool returned an unexpected tool id")
        if approval is not None:
            result = result.model_copy(update={"approval_status": "approved"})
        return await self._finish(
            call,
            actor,
            result,
            duration_ms=int((perf_counter() - started) * 1_000),
            definition=definition,
            approved_by=approval.approved_by if approval else None,
        )

    async def _finish(
        self,
        call: ToolCall,
        actor: RequestActor,
        result: ToolResult,
        duration_ms: int = 0,
        definition: ToolDefinition | None = None,
        approved_by: str | None = None,
    ) -> ToolResult:
        await self._audit.append(
            AuditRecord(
                tool_id=call.tool_id,
                connector_id=definition.connector_id if definition else None,
                actor_id=actor.user_id or "anonymous",
                approved_by=approved_by,
                argument_names=tuple(argument.name for argument in call.arguments),
                status=result.status,
                execution_id=call.execution_id,
                duration_ms=duration_ms,
                summary=f"tool result: {result.status}",
            )
        )
        return result
