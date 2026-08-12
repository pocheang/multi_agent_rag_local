"""Contract tests for the versioned orchestration SSE boundary."""

import json
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.routes.orchestration import serialize_execution_event
from app.api.runtime import get_app_services
from app.domain.contracts import ToolResult
from app.domain.events import EventMetadata, ExecutionEvent
from app.main import app
from app.mcp.contracts import ToolCall, ToolDefinition
from app.orchestration.request import RequestActor
from app.services.agent_execution_tracker import AgentExecutionTracker


def test_sse_serializes_only_the_versioned_execution_event() -> None:
    """SSE must never expose a raw compatibility payload or connector secret."""
    event = ExecutionEvent(
        stage="tool",
        status="completed",
        duration_ms=12,
        message="approval required",
        metadata=(EventMetadata(key="tool_id", value="querymind_crm_write_note"),),
    )

    payload = serialize_execution_event(event)

    assert payload.startswith("event: execution_event\ndata: ")
    encoded = payload.removeprefix("event: execution_event\ndata: ").strip()
    assert json.loads(encoded) == event.model_dump(mode="json")
    assert "compatibility_payload" not in payload
    assert "secret" not in payload


def test_execution_trace_endpoint_streams_only_versioned_safe_events() -> None:
    """Leaking tracker input/output data through the trace SSE endpoint is forbidden."""
    tracker = AgentExecutionTracker.get_instance()
    tracker.clear_all_traces()
    execution_id = tracker.start_execution("question", user_id="trace-user")
    step_id = tracker.record_agent_step(
        execution_id,
        "router",
        input_data={"credential_secret": "must-not-leak"},
    )
    tracker.complete_agent_step(execution_id, step_id, output_data={"compatibility_payload": "must-not-leak"})
    tracker.complete_execution(execution_id)

    response = TestClient(app).get(
        f"/api/v1/orchestration/executions/{execution_id}/events",
        headers={"X-Test-User": "trace-user", "X-Test-Role": "viewer", "X-Test-User-Id": "trace-user"},
    )

    assert response.status_code == 200
    payloads = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    assert len(payloads) == 2
    assert all(payload["version"] == "1" for payload in payloads)
    assert all("credential_secret" not in payload for payload in payloads)
    assert all("compatibility_payload" not in payload for payload in payloads)


@pytest.mark.asyncio
async def test_governed_approval_is_published_to_its_execution_sse_stream() -> None:
    """Dropping the approval-required event leaves the browser unable to request approval."""
    tracker = AgentExecutionTracker.get_instance()
    tracker.clear_all_traces()
    execution_id = tracker.start_execution("send update", user_id="trace-user")
    services = get_app_services(app)
    tool_id = "querymind_connector_trace_send_update"

    async def should_not_run(call: ToolCall, actor: RequestActor) -> ToolResult:
        del call, actor
        raise AssertionError("an approval-required invocation must not execute the tool")

    services.tool_registry.register(ToolDefinition(tool_id=tool_id, operation="send"), should_not_run)
    result = await services.gateway.invoke(
        ToolCall(tool_id=tool_id, execution_id=execution_id), RequestActor(user_id="trace-user")
    )
    tracker.complete_execution(execution_id)

    response = TestClient(app).get(
        f"/api/v1/orchestration/executions/{execution_id}/events",
        headers={"X-Test-User": "trace-user", "X-Test-Role": "viewer", "X-Test-User-Id": "trace-user"},
    )

    payloads = [json.loads(line.removeprefix("data: ")) for line in response.text.splitlines() if line.startswith("data: ")]
    approval = next(payload for payload in payloads if payload["message"] == "approval required")
    assert response.status_code == 200
    assert result.status == "approval_required"
    assert approval == {
        "version": "1",
        "stage": "tool",
        "status": "skipped",
        "duration_ms": 0,
        "message": "approval required",
        "metadata": [{"key": "approval_request_id", "value": result.approval_token}],
        "occurred_at": approval["occurred_at"],
    }


def test_normal_stream_query_emits_approval_for_real_owned_connector_disable_tool() -> None:
    """Leaving the production registry/tool adapter disconnected would emit no approval for this real operation."""
    owner_id = f"tool-owner-{uuid4().hex}"
    connector_id = "crm"
    services = get_app_services(app)
    services.connectors.create(
        connector_id=connector_id,
        owner_id=owner_id,
        name="Production CRM",
        base_url="https://93.184.216.34/health",
        allowed_hosts=frozenset({"93.184.216.34"}),
        secret="production-tool-secret",
    )

    response = TestClient(app).post(
        "/api/query/stream",
        data={"question": f"Disable connector {connector_id}"},
        headers={
            "X-Test-User": owner_id,
            "X-Test-Role": "viewer",
            "X-Test-User-Id": owner_id,
        },
    )

    payloads = [json.loads(line.removeprefix("data: ")) for line in response.text.splitlines() if line.startswith("data: ")]
    assert payloads
    assert all(payload["version"] == "1" for payload in payloads)
    assert all("type" not in payload and "result" not in payload for payload in payloads)
    started = next(payload for payload in payloads if payload["message"] == "execution started")
    execution_id = next(item["value"] for item in started["metadata"] if item["key"] == "execution_id")
    approval_events = [
        event
        for event in services.execution_events.events_since(execution_id, 0)
        if event.message == "approval required"
    ]

    assert response.status_code == 200
    assert len(approval_events) == 1
    assert approval_events[0].stage == "tool"
    assert approval_events[0].metadata[0].key == "approval_request_id"
    assert services.connectors.list_for_owner(owner_id)[0].status == "enabled"
