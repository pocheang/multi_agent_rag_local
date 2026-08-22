"""Replay, result-cache, and in-flight handling for query streams."""

from __future__ import annotations

from typing import Any

from fastapi import Request
from fastapi.responses import StreamingResponse

from app.api.dependencies import QueryRuntime, _sse_response, _trace_id, runtime_metrics
from app.api.query.response import ensure_trackable_execution_result
from app.api.transport.errors import conflict
from app.graph.streaming import encode_sse
from app.services.observability.alerting import emit_alert


def cached_stream_response(
    *,
    stream_cache_key: str,
    replay_enabled: bool,
    is_fast_smalltalk: bool,
    request: Request,
    user: dict[str, Any],
    session_id: str | None,
    original_question: str,
    query_runtime: QueryRuntime,
) -> StreamingResponse | None:
    """Return a replay/result-cache stream when one is available."""
    query_result_cache = query_runtime.query_result_cache
    if replay_enabled and not is_fast_smalltalk:
        replay = query_result_cache.get_stream_events(stream_cache_key)
        replay_events = list(replay.get("events", []) or [])
        replay_done = bool(replay.get("done", False))
        if replay_events and replay_done:

            async def event_gen_replay():
                for event in replay_events:
                    if isinstance(event, dict):
                        yield encode_sse(event)

            return _sse_response(event_gen_replay(), append_terminal_event=True)

    cached = (
        None
        if is_fast_smalltalk
        else query_result_cache.get(
            stream_cache_key,
            session_id=session_id,
            user_id=str(user.get("user_id", "")),
        )
    )
    if not isinstance(cached, dict) or not cached.get("result"):
        return None

    runtime_metrics.inc("query_stream_cache_hit_total")
    done_result = ensure_trackable_execution_result(
        dict(cached.get("result", {}) or {}),
        question=original_question,
        user=user,
    )

    async def event_gen_cached():
        yield encode_sse({"type": "status", "message": "cache_hit"})
        answer = str(done_result.get("answer", "") or "")
        if answer:
            yield encode_sse({"type": "answer_chunk", "content": answer})
        yield encode_sse({"type": "done", "result": done_result})

    return _sse_response(event_gen_cached(), append_terminal_event=True)


def claim_stream(
    *,
    stream_cache_key: str,
    request: Request,
    user: dict[str, Any],
    session_id: str | None,
    query_runtime: QueryRuntime,
) -> None:
    """Claim one stream cache key or reject a duplicate in-flight request."""
    query_result_cache = query_runtime.query_result_cache
    if query_result_cache.mark_inflight(stream_cache_key):
        replay = query_result_cache.get_stream_events(stream_cache_key)
        if replay.get("events") and not replay.get("done", False):
            query_result_cache.clear_stream_events(stream_cache_key)
        return
    runtime_metrics.inc("query_stream_duplicate_total")
    emit_alert(
        "query_stream_duplicate_inflight",
        {"trace_id": _trace_id(request), "session_id": str(session_id or "")},
    )
    raise conflict("duplicate request in progress")


__all__ = ["cached_stream_response", "claim_stream"]
