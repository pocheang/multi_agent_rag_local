"""Versioned SSE transport for public query streams."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

from fastapi.responses import StreamingResponse

from app.domain.events import EventMetadata, ExecutionEvent


def serialize_compatibility_event(event: dict[str, Any]) -> dict[str, Any]:
    """Project engine-neutral stream frames into the public safe SSE contract."""
    if event.get("version") == "1" and {"stage", "status"}.issubset(event):
        return ExecutionEvent.model_validate(event).model_dump(mode="json")

    event_type = str(event.get("type", "") or "")
    stage = str(event.get("stage", "") or "")
    message = str(event.get("message", "") or "")
    metadata: list[EventMetadata] = []
    if event_type == "execution_started":
        stage, status, message = "route", "skipped", "execution started"
        if event.get("execution_id"):
            metadata.append(EventMetadata(key="execution_id", value=str(event["execution_id"])))
    elif event_type == "answer_chunk":
        stage, status = "synthesize", "completed"
        content = str(event.get("content", ""))
        if content:
            metadata.append(EventMetadata(key="content", value=content[:1000]))
    elif event_type == "done":
        stage, status, message = "complete", "completed", "execution completed"
    elif event_type == "error":
        stage, status = "failed", "failed"
        message = message or "query stream failed"
    else:
        stage = stage if stage in {"route", "plan", "rag", "tool", "synthesize", "complete", "failed"} else "rag"
        status = str(event.get("status", "completed") or "completed")
        status = status if status in {"completed", "failed", "skipped"} else "completed"
    return ExecutionEvent(
        stage=stage,
        status=status,
        duration_ms=max(0, int(event.get("duration_ms", 0) or 0)),
        message=message[:1000],
        metadata=tuple(metadata),
    ).model_dump(mode="json")


async def _versioned_events(body: AsyncIterator[str | bytes]) -> AsyncIterator[bytes]:
    """Expose only the versioned execution-event schema over SSE."""
    async for chunk in body:
        raw = chunk.decode("utf-8") if isinstance(chunk, bytes) else chunk
        if not raw.startswith("data: "):
            yield raw.encode("utf-8")
            continue
        try:
            event = json.loads(raw.removeprefix("data: ").strip())
        except json.JSONDecodeError:
            yield raw.encode("utf-8")
            continue
        payload = json.dumps(serialize_compatibility_event(event), ensure_ascii=False)
        yield f"data: {payload}\n\n".encode()


def versioned_stream_response(response: StreamingResponse) -> StreamingResponse:
    """Expose the established versioned SSE contract without projection loss."""
    return StreamingResponse(
        _versioned_events(response.body_iterator),
        status_code=response.status_code,
        media_type=response.media_type,
        headers=dict(response.headers),
        background=response.background,
    )


__all__ = ["serialize_compatibility_event", "versioned_stream_response"]

