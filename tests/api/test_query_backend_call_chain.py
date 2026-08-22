"""Regression tests for the current typed HTTP-to-pipeline query chain."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from app.api.main import app
from app.pipeline.contracts import PipelineResult, PipelineRoute


def _result() -> PipelineResult:
    return PipelineResult(
        answer="typed answer",
        citations=(),
        route=PipelineRoute(route="vector", reason="test"),
        execution_metadata={},
    )


def test_normal_query_uses_prepared_sync_boundary_and_returns_trackable_id():
    headers = {
        "X-Test-User": "typed-query-user",
        "X-Test-User-Id": "typed-query-user",
        "X-Test-Role": "viewer",
    }
    with patch(
        "app.pipeline.rag_pipeline.RAGPipeline.execute_prepared_standard_sync",
        return_value=_result(),
    ):
        response = TestClient(app).post(
            "/query",
            headers=headers,
            json={"question": "What is the typed query path?"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["answer"] == "typed answer"
    assert payload["route"] == "vector"
    assert payload["execution_id"]


def test_stream_execution_marks_trace_complete_after_done_event(monkeypatch):
    import asyncio
    from types import SimpleNamespace

    from app.api.query.streaming import execution
    from app.services.observability.agent_execution_tracker import AgentExecutionTracker

    execution_id = "stream-trace-regression"
    tracker = AgentExecutionTracker.get_instance()
    tracker.start_execution("stream question", execution_id=execution_id, user_id="stream-user")

    class _Guard:
        def acquire(self, _key):
            from contextlib import nullcontext
            return nullcontext()

    class _Pipeline:
        async def execute_stream(self, _request, *, execution_id):
            yield {"type": "done", "result": {"answer": "done", "execution_id": execution_id}}

    monkeypatch.setattr(execution, "query_guard", _Guard())
    monkeypatch.setattr(execution, "_query_limiter_key", lambda *_args: "stream-user")
    monkeypatch.setattr(execution, "_is_overload_mode", lambda: False)
    monkeypatch.setattr(execution.query_result_cache, "clear_inflight", lambda _key: None)
    monkeypatch.setattr(execution.query_result_cache, "set", lambda *_args, **_kwargs: None)

    context = execution.StreamExecutionContext(
        request=SimpleNamespace(state=SimpleNamespace(trace_id="trace"), headers={}),
        user={"user_id": "stream-user"},
        session_id=None,
        original_question="stream question",
        effective_question="stream question",
        normalized_strategy=None,
        strategy_meta={},
        stream_cache_key="stream-key",
        replay_enabled=False,
        runtime_api_settings=None,
        execution_id=execution_id,
        history_store=None,
        pipeline=_Pipeline(),
        pipeline_request=object(),
        preparation=None,
        source_scope_audit=lambda *_args: None,
        result_signer=lambda *_args: (None, None),
    )

    async def _consume():
        return [event async for event in execution.stream_execution_events(context)]

    asyncio.run(_consume())
    assert tracker.get_execution_trace(execution_id).status == "completed"
