import asyncio
import json
import logging
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.api.dependencies import _require_permission, _require_user
from app.api.transport.errors import bad_request, forbidden, not_found
from app.services.observability.agent_execution_tracker import (
    AgentExecutionTracker,
    ExecutionTrace,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent-tracking", tags=["agent-tracking"])


def _verify_trace_ownership(trace: ExecutionTrace, user: dict[str, Any]) -> None:
    """
    Verify that the user has permission to access this trace.

    Regular users can only access their own traces.
    Admins can access all traces.

    Raises:
        HTTPException: If user doesn't have permission to access the trace.
    """
    role = str(user.get("role", "viewer")).lower()
    if role == "admin":
        return

    user_id = str(user.get("user_id", ""))
    trace_user_id = str(trace.user_id or "")

    if user_id != trace_user_id:
        raise forbidden("You do not have permission to access this execution trace")


class ExecutionStatus(BaseModel):
    execution_id: str
    status: str
    query: str
    step_count: int
    start_time: str
    end_time: str | None = None
    total_duration_ms: float | None = None


@router.get("/stream/{execution_id}")
async def stream_execution(
    execution_id: str, request: Request, user: dict[str, Any] = Depends(_require_user), max_iterations: int = 600
):
    """
    Server-Sent Events (SSE) endpoint for real-time execution tracking.

    Streams agent steps as they complete during execution.
    User can only stream their own executions unless they are admin.
    """
    _require_permission(user, "query:run", request, "agent-tracking")
    tracker = AgentExecutionTracker.get_instance()
    max_iterations = max(1, min(int(max_iterations or 600), 600))

    # Verify ownership before streaming
    trace = tracker.get_execution_trace(execution_id)
    if not trace:
        raise not_found("Execution not found")
    _verify_trace_ownership(trace, user)

    async def event_generator():
        last_step_count = 0
        heartbeat_counter = 0
        iteration = 0

        while iteration < max_iterations:
            iteration += 1
            trace = tracker.get_execution_trace(execution_id)

            if not trace:
                yield f"event: error\ndata: {json.dumps({'error': 'Execution not found'})}\n\n"
                break

            if iteration == 1:
                yield f"event: heartbeat\ndata: {json.dumps({'timestamp': trace.start_time.isoformat()})}\n\n"

            if len(trace.steps) > last_step_count:
                for step in trace.steps[last_step_count:]:
                    step_data = step.model_dump(mode="json")
                    yield f"event: agent_step\ndata: {json.dumps(step_data)}\n\n"
                last_step_count = len(trace.steps)

            if trace.status in ["completed", "failed"]:
                trace_data = trace.model_dump(mode="json")
                yield f"event: execution_complete\ndata: {json.dumps(trace_data)}\n\n"
                break

            heartbeat_counter += 1
            if heartbeat_counter >= 30:
                yield f"event: heartbeat\ndata: {json.dumps({'timestamp': trace.start_time.isoformat()})}\n\n"
                heartbeat_counter = 0

            await asyncio.sleep(0.5)

        if iteration >= max_iterations:
            yield f"event: timeout\ndata: {json.dumps({'message': 'Stream timeout'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/trace/{execution_id}", response_model=ExecutionTrace)
async def get_execution_trace(execution_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
    """
    Get the complete execution trace for a given execution ID.
    User can only view their own executions unless they are admin.
    """
    _require_permission(user, "query:run", request, "agent-tracking")
    tracker = AgentExecutionTracker.get_instance()
    trace = tracker.get_execution_trace(execution_id)

    if not trace:
        raise not_found("Execution not found")

    _verify_trace_ownership(trace, user)
    return trace


@router.get("/history", response_model=list[ExecutionTrace])
async def get_execution_history(request: Request, user: dict[str, Any] = Depends(_require_user), limit: int = 20):
    """
    Get recent execution traces.
    Users see only their own executions; admins see all.
    """
    _require_permission(user, "query:run", request, "agent-tracking")
    if limit < 1 or limit > 100:
        raise bad_request("Limit must be between 1 and 100")

    tracker = AgentExecutionTracker.get_instance()
    all_traces = tracker.get_recent_executions(limit=limit * 2)  # Get more to filter

    # Filter by user unless admin
    role = str(user.get("role", "viewer")).lower()
    if role != "admin":
        user_id = str(user.get("user_id", ""))
        # Note: This assumes ExecutionTrace has a user_id field.
        # If not, all users will see all traces. Need to verify the model.
        filtered_traces = [t for t in all_traces if getattr(t, "user_id", None) == user_id]
        return filtered_traces[:limit]

    return all_traces[:limit]


@router.get("/status/{execution_id}", response_model=ExecutionStatus)
async def get_execution_status(execution_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
    """
    Get the current status of an execution.
    User can only view their own executions unless they are admin.
    """
    _require_permission(user, "query:run", request, "agent-tracking")
    tracker = AgentExecutionTracker.get_instance()
    trace = tracker.get_execution_trace(execution_id)

    if not trace:
        raise not_found("Execution not found")

    _verify_trace_ownership(trace, user)

    return ExecutionStatus(
        execution_id=trace.execution_id,
        status=trace.status,
        query=trace.query,
        step_count=len(trace.steps),
        start_time=trace.start_time.isoformat(),
        end_time=trace.end_time.isoformat() if trace.end_time else None,
        total_duration_ms=trace.total_duration_ms,
    )


@router.delete("/trace/{execution_id}")
async def delete_execution_trace(execution_id: str, request: Request, user: dict[str, Any] = Depends(_require_user)):
    """
    Delete a specific execution trace.
    User can only delete their own executions unless they are admin.
    """
    _require_permission(user, "query:run", request, "agent-tracking")
    tracker = AgentExecutionTracker.get_instance()
    trace = tracker.get_execution_trace(execution_id)

    if not trace:
        raise not_found("Execution not found")

    _verify_trace_ownership(trace, user)

    with tracker._traces_lock:
        del tracker._traces[execution_id]

    return {"message": "Execution trace deleted", "execution_id": execution_id}


@router.post("/cleanup")
async def cleanup_old_traces(request: Request, user: dict[str, Any] = Depends(_require_user)):
    """
    Manually trigger cleanup of old execution traces - Admin only.
    """
    _require_permission(user, "admin:ops_manage", request, "admin")
    tracker = AgentExecutionTracker.get_instance()
    removed_count = tracker.cleanup_old_traces()

    return {"message": f"Cleaned up {removed_count} old execution traces", "removed_count": removed_count}


