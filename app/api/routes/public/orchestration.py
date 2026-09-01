"""Versioned, safe Server-Sent Event delivery for orchestration traces."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, Request
from fastapi.responses import StreamingResponse

from app.api.deps.runtime import get_answer_stream_store, get_execution_event_store, require_trace_actor
from app.api.transport.errors import forbidden, not_found
from app.domain.events import ExecutionEvent
from app.orchestration.answer_stream import AnswerStreamStore
from app.orchestration.execution_events import ExecutionEventStore
from app.orchestration.request import RequestActor
from app.services.observability.agent_execution_tracker import AgentExecutionTracker, AgentStep, ExecutionTrace

router = APIRouter(prefix="/api/v1/orchestration", tags=["orchestration"])


_STAGE_BY_AGENT: tuple[tuple[str, Literal["route", "plan", "rag", "tool", "synthesize"]], ...] = (
    ("router", "route"),
    ("planner", "plan"),
    ("plan", "plan"),
    ("tool", "tool"),
    ("synth", "synthesize"),
)


def serialize_answer_fragment(fragment: str) -> str:
    """Serialize one already-redacted draft fragment for the SSE wire format.

    A distinct event name so a client cannot mistake a draft for a finished
    answer: these carry no citation numbering and no reference list, both of
    which are decided in `output_filter` once the whole answer exists.
    """
    payload = json.dumps({"text": fragment}, ensure_ascii=False, separators=(",", ":"))
    return f"event: answer_fragment\ndata: {payload}\n\n"


def serialize_execution_event(event: ExecutionEvent) -> str:
    """Serialize exactly one safe execution event for the SSE wire format."""
    payload = json.dumps(event.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))
    return f"event: execution_event\ndata: {payload}\n\n"


def _trace_event(step: AgentStep) -> ExecutionEvent:
    """Map legacy tracker detail to a non-sensitive, immutable trace event."""
    stage = next((value for prefix, value in _STAGE_BY_AGENT if step.agent_name.lower().startswith(prefix)), "rag")
    status = (
        "failed" if step.status in {"failed", "error"} else "completed" if step.status == "completed" else "skipped"
    )
    return ExecutionEvent(
        stage=stage,
        status=status,
        duration_ms=max(0, int(step.duration_ms or 0)),
        occurred_at=step.end_time or step.start_time,
    )


def _ensure_trace_access(trace: ExecutionTrace, actor: RequestActor) -> None:
    """Keep execution trace visibility aligned with the existing tracker policy."""
    if str(actor.role or "").lower() == "admin":
        return
    if str(actor.user_id or "") != str(trace.user_id or ""):
        raise forbidden("You do not have permission to access this execution trace")


@router.get("/executions/{execution_id}/events")
async def stream_execution_events(
    execution_id: Annotated[str, Path(max_length=128)],
    request: Request,
    actor: RequestActor = Depends(require_trace_actor),
    event_store: ExecutionEventStore = Depends(get_execution_event_store),
    answer_store: AnswerStreamStore = Depends(get_answer_stream_store),
) -> StreamingResponse:
    """Follow safe events for one execution until it reaches a terminal state."""
    trace = AgentExecutionTracker.get_instance().get_execution_trace(execution_id)
    if trace is None:
        raise not_found("Execution")
    _ensure_trace_access(trace, actor)

    async def event_stream():
        legacy_offset = 0
        event_offset = 0
        answer_offset = 0
        while True:
            current_trace = AgentExecutionTracker.get_instance().get_execution_trace(execution_id)
            if current_trace is None:
                return
            steps = tuple(current_trace.steps)
            for step in steps[legacy_offset:]:
                yield serialize_execution_event(_trace_event(step))
            legacy_offset = len(steps)
            events = event_store.events_since(execution_id, event_offset)
            for event in events:
                yield serialize_execution_event(event)
            event_offset += len(events)
            # Same subscription, same access check: a client watching the trace is
            # already watching the draft.
            fragments = answer_store.since(execution_id, answer_offset)
            for fragment in fragments:
                yield serialize_answer_fragment(fragment)
            answer_offset += len(fragments)
            if current_trace.status in {"completed", "failed"}:
                yield serialize_execution_event(
                    ExecutionEvent(
                        stage="complete" if current_trace.status == "completed" else "failed",
                        status=current_trace.status,
                        duration_ms=max(0, int(current_trace.total_duration_ms or 0)),
                        occurred_at=current_trace.end_time or current_trace.start_time,
                    )
                )
                return
            if await request.is_disconnected():
                return
            await asyncio.sleep(0.05)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive", "X-Accel-Buffering": "no"},
    )
