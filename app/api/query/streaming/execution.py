"""Pipeline execution and finalization for public query streams."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass
from typing import Any

from fastapi import Request

from app.api.dependencies import (
    QueryRuntime,
    _is_overload_mode,
    _promote_long_term_memory,
    _query_limiter_key,
    _trace_id,
    get_query_runtime,
    runtime_metrics,
)
from app.graph.streaming.sse_encoder import encode_sse
from app.services.observability.agent_execution_tracker import AgentExecutionTracker
from app.services.observability.alerting import emit_alert
from app.services.query_guard import QueryOverloadedError, QueryRateLimitedError
from app.services.runtime.request_context import request_context

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StreamExecutionContext:
    """All validated values needed after a stream has claimed its cache key."""

    request: Request
    user: dict[str, Any]
    session_id: str | None
    original_question: str
    effective_question: str
    normalized_strategy: str | None
    strategy_meta: Mapping[str, Any]
    stream_cache_key: str
    replay_enabled: bool
    runtime_api_settings: Mapping[str, Any] | None
    execution_id: str
    history_store: Any
    pipeline: Any
    pipeline_request: Any
    preparation: Any | None
    source_scope_audit: Any
    result_signer: Any
    credit_reservation: Any | None = None
    query_runtime: QueryRuntime | None = None


async def stream_execution_events(context: StreamExecutionContext) -> AsyncIterator[str]:
    """Yield compatibility events while owning cleanup and final persistence."""
    final_result: dict[str, Any] | None = None
    trace_id = _trace_id(context.request)
    limiter_key = _query_limiter_key(context.user, context.request)
    query_runtime = context.query_runtime or get_query_runtime()
    overload_mode = _is_overload_mode(query_runtime)
    tracker = AgentExecutionTracker.get_instance()
    query_guard = query_runtime.query_guard
    query_result_cache = query_runtime.query_result_cache
    settings = query_runtime.settings
    try:
        with query_guard.acquire(limiter_key):
            with request_context(
                timeout_ms=int(getattr(settings, "query_request_timeout_ms", 20000) or 20000),
                overload_mode=overload_mode,
                api_settings=context.runtime_api_settings,
            ):
                hello_event = {"type": "status", "message": "trace", "trace_id": trace_id}
                yield encode_sse({"type": "execution_started", "execution_id": context.execution_id})
                if context.replay_enabled:
                    query_result_cache.append_stream_event(context.stream_cache_key, hello_event, done=False)
                yield encode_sse(hello_event)
                if context.preparation is None:
                    events = context.pipeline.execute_stream(
                        context.pipeline_request,
                        execution_id=context.execution_id,
                    )
                else:
                    prepared = context.pipeline.bind_standard_runtime_context(
                        context.preparation,
                        user=context.user,
                        overload_mode=overload_mode,
                        source_scope_audit=context.source_scope_audit,
                        result_signer=context.result_signer,
                        trace_id=trace_id,
                    )
                    events = context.pipeline.execute_prepared_standard_stream(
                        prepared,
                        execution_id=context.execution_id,
                    )
                async for event in events:
                    if event.get("type") == "done":
                        final_result = dict(event.get("result", {}) or {})
                        if context.credit_reservation is not None:
                            context.credit_reservation.commit()
                        if context.replay_enabled:
                            query_result_cache.append_stream_event(context.stream_cache_key, event, done=True)
                            query_result_cache.mark_stream_done(context.stream_cache_key)
                    elif context.replay_enabled:
                        query_result_cache.append_stream_event(context.stream_cache_key, event, done=False)
                    yield encode_sse(event)
    except QueryRateLimitedError as exc:
        tracker.fail_execution(context.execution_id, str(exc))
        runtime_metrics.inc("query_stream_rate_limited_total")
        emit_alert("query_stream_rate_limited", {"message": str(exc), "trace_id": trace_id})
        yield encode_sse({"type": "error", "error": "rate_limited", "message": str(exc)})
        return
    except QueryOverloadedError as exc:
        tracker.fail_execution(context.execution_id, str(exc))
        runtime_metrics.inc("query_stream_overloaded_total")
        emit_alert("query_stream_overloaded", {"message": str(exc), "trace_id": trace_id})
        yield encode_sse({"type": "error", "error": "overloaded", "message": str(exc)})
        return
    except asyncio.CancelledError:
        tracker.fail_execution(context.execution_id, "stream cancelled before completion")
        raise
    except Exception as exc:
        tracker.fail_execution(context.execution_id, f"{type(exc).__name__}: {exc}")
        runtime_metrics.inc("query_stream_internal_error_total")
        logger.exception("query stream unexpected failure")
        emit_alert(
            "query_stream_internal_error",
            {"message": f"{type(exc).__name__}: {exc}", "trace_id": trace_id},
        )
        yield encode_sse(
            {
                "type": "error",
                "error": "internal_error",
                "message": "query stream failed unexpectedly; please retry.",
                "trace_id": trace_id,
            }
        )
        return
    finally:
        query_result_cache.clear_inflight(context.stream_cache_key)
        if context.credit_reservation is not None:
            context.credit_reservation.close()

    if context.session_id and final_result is not None:
        context.history_store.append_message(
            context.session_id,
            "assistant",
            final_result.get("answer", ""),
            metadata=_history_metadata(final_result, context),
        )
        _promote_long_term_memory(
            user=context.user,
            session_id=context.session_id,
            question=context.original_question,
            result=final_result,
        )
    if final_result is not None:
        query_result_cache.set(
            context.stream_cache_key,
            {"result": final_result},
            session_id=context.session_id,
            user_id=str(context.user.get("user_id", "")),
        )
        runtime_metrics.inc("query_stream_success_total")
        tracker.complete_execution(context.execution_id, final_result)
    else:
        tracker.fail_execution(context.execution_id, "stream ended without a final result")


def _history_metadata(result: dict[str, Any], context: StreamExecutionContext) -> dict[str, Any]:
    return {
        "route": result.get("route", "unknown"),
        "execution_route": result.get("execution_route", ""),
        "agent_class": result.get("agent_class", "general"),
        "web_used": result.get("web_result", {}).get("used", False),
        "thoughts": result.get("thoughts", []),
        "graph_entities": result.get("graph_result", {}).get("entities", []),
        "citations": result.get("vector_result", {}).get("citations", [])
        + result.get("web_result", {}).get("citations", []),
        "retrieval_diagnostics": result.get("vector_result", {}).get("retrieval_diagnostics", {}),
        "grounding": result.get("grounding", {}),
        "explainability": result.get("explainability", {}),
        "answer_safety": result.get("answer_safety", {}),
        "retrieval_strategy": context.normalized_strategy or "advanced",
        "retrieval_strategy_reason": context.strategy_meta.get("reason"),
        "retrieval_strategy_bucket": context.strategy_meta.get("bucket"),
        "evidence_conflict": result.get("evidence_conflict", {}),
        "source_scope": result.get("source_scope", {}),
    }


__all__ = ["StreamExecutionContext", "stream_execution_events"]
