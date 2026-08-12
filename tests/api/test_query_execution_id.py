"""Tests for execution_id in query responses."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.pipeline.contracts import PipelineResult, PipelineRoute
from app.services.agent_execution_tracker import AgentExecutionTracker


@pytest.fixture(autouse=True)
def clear_tracker():
    """Clear tracker before and after each test."""
    tracker = AgentExecutionTracker.get_instance()
    tracker.clear_all_traces()
    yield
    tracker.clear_all_traces()


@pytest.fixture
def user_headers():
    """Mock user headers."""
    return {"X-Test-User": "testuser", "X-Test-Role": "viewer", "X-Test-User-Id": "test-123"}


@pytest.fixture
def mock_run_query():
    """Mock the unified pipeline to return a simple tracked answer."""
    with patch("app.api.routes.query_request_execution.RAGPipeline.execute_sync") as mock:

        def side_effect(question, **kwargs):
            execution_id = kwargs.get("execution_id") or "test-exec-id"
            payload = {
                "answer": "Test answer",
                "route": "vector",
                "reason": "test",
                "skill": "test",
                "agent_class": "general",
                "execution_id": execution_id,
                "vector_result": {"citations": [], "retrieved_count": 0},
                "graph_result": {"entities": []},
                "web_result": {"used": False, "citations": []},
                "detected_language": "zh",
            }
            return PipelineResult(
                answer=payload["answer"],
                citations=(),
                route=PipelineRoute(route=payload["route"]),
                execution_metadata={"compatibility_payload": payload},
            )

        mock.side_effect = side_effect
        yield mock


def test_query_endpoint_returns_execution_id(user_headers, mock_run_query):
    """Test that /query endpoint returns execution_id in response."""
    client = TestClient(app)

    response = client.post(
        "/api/query", json={"question": "test question", "session_id": "test-session"}, headers=user_headers
    )

    assert response.status_code == 200
    data = response.json()

    assert data["answer"] == "Test answer"
    assert data["citations"] == []
    assert data["route"] == "vector"

    # Verify execution_id is present
    assert "execution_id" in data
    assert data["execution_id"] is not None


def test_stream_query_exposes_execution_id_before_workflow_completion(user_headers):
    """The browser must be able to attach an execution trace before the final answer arrives."""
    pipeline_calls = []

    async def stream_generator(_pipeline, pipeline_request, *, execution_id):
        pipeline_calls.append((pipeline_request, execution_id))
        yield {"type": "status", "message": "routing"}
        yield {"type": "route", "route": "vector"}
        yield {
            "type": "done",
            "result": {
                "answer": "Test answer",
                "route": "vector",
                "execution_id": execution_id,
                "vector_result": {},
                "graph_result": {},
                "web_result": {"used": False},
                "detected_language": "zh",
            },
        }

    with (
        patch("app.api.routes.query_stream.RAGPipeline.execute_stream", new=stream_generator),
        patch(
            "app.api.routes.query_stream.run_query_stream",
            side_effect=AssertionError("query route must not invoke the compatibility stream directly"),
            create=True,
        ) as direct_stream,
    ):
        client = TestClient(app)
        response = client.post(
            "/api/query/stream", data={"question": "test question", "session_id": "test-session"}, headers=user_headers
        )

        # Parse SSE events
        lines = response.text.strip().split("\n")
        events = []
        current_event = {}

        for line in lines:
            if line.startswith("event:"):
                current_event["event"] = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                import json

                current_event["data"] = json.loads(line.split(":", 1)[1].strip())
            elif line == "":
                if current_event:
                    events.append(current_event)
                    current_event = {}

        versioned_events = [e["data"] for e in events if e.get("event") == "execution_event"]
        assert versioned_events
        assert all(event["version"] == "1" for event in versioned_events)
        started_event = next(event for event in versioned_events if event["message"] == "execution started")
        started_execution_id = next(
            metadata["value"] for metadata in started_event["metadata"] if metadata["key"] == "execution_id"
        )
        assert isinstance(started_execution_id, str) and started_execution_id
        assert len(pipeline_calls) == 1
        assert pipeline_calls[0][1] == started_execution_id
        assert pipeline_calls[0][0].question.startswith("test question")
        direct_stream.assert_not_called()

        assert any(event["stage"] == "complete" for event in versioned_events)
        assert all("result" not in event for event in versioned_events)


def test_execution_id_can_be_used_with_tracking_endpoints(user_headers, mock_run_query):
    """Test that execution_id from query can be used with agent-tracking endpoints."""
    tracker = AgentExecutionTracker.get_instance()

    # Create a real execution trace
    exec_id = tracker.start_execution("test question", user_id="test-123")
    tracker.complete_execution(exec_id, {"answer": "test"})

    # Mock run_query to return this execution_id
    def side_effect(question, **kwargs):
        payload = {
            "answer": "Test answer",
            "route": "vector",
            "reason": "test",
            "skill": "test",
            "agent_class": "general",
            "execution_id": exec_id,
            "vector_result": {"citations": [], "retrieved_count": 0},
            "graph_result": {"entities": []},
            "web_result": {"used": False, "citations": []},
            "detected_language": "zh",
        }
        return PipelineResult(
            answer=payload["answer"],
            citations=(),
            route=PipelineRoute(route=payload["route"]),
            execution_metadata={"compatibility_payload": payload},
        )

    mock_run_query.side_effect = side_effect

    client = TestClient(app)

    # Make a query
    query_response = client.post(
        "/api/query", json={"question": "test question", "session_id": "test-session"}, headers=user_headers
    )

    assert query_response.status_code == 200
    execution_id = query_response.json()["execution_id"]

    # Use the execution_id with tracking endpoint
    trace_response = client.get(f"/api/agent-tracking/trace/{execution_id}", headers=user_headers)

    assert trace_response.status_code == 200
    trace_data = trace_response.json()
    assert trace_data["execution_id"] == execution_id
    assert trace_data["query"] == "test question"


def test_execution_id_persists_through_workflow(user_headers):
    """Test that execution_id is created and persists through the entire workflow."""
    tracker = AgentExecutionTracker.get_instance()

    # We can't easily test the full workflow without mocking everything,
    # but we can verify the tracker creates and maintains execution_id
    exec_id = tracker.start_execution("workflow test", user_id="test-123")

    # Simulate workflow steps
    step_id = tracker.record_agent_step(exec_id, "router", {"question": "test"})
    tracker.complete_agent_step(exec_id, step_id, {"route": "vector"})

    # Complete execution
    final_result = {"answer": "final answer", "route": "vector"}
    tracker.complete_execution(exec_id, final_result)

    # Retrieve and verify
    trace = tracker.get_execution_trace(exec_id)
    assert trace is not None
    assert trace.execution_id == exec_id
    assert len(trace.steps) == 1
    assert trace.status == "completed"
    assert trace.metadata.get("result") == final_result
