"""Contract tests for browser-facing connector approval APIs."""

from datetime import UTC, datetime, timedelta
from importlib import import_module

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.routes.connectors import router
from app.domain.contracts import ToolResult
from app.main import app
from app.mcp.contracts import ToolCall, ToolDefinition
from app.orchestration.request import RequestActor


def get_app_services(app):
    return import_module("app.api.runtime").get_app_services(app)


HEADERS = {
    "X-Test-User": "approval-user",
    "X-Test-Role": "viewer",
    "X-Test-User-Id": "approval-user",
}


@pytest.mark.asyncio
async def test_production_registry_and_approval_api_share_store_without_executing_tool() -> None:
    """Using another store, or invoking on POST, must fail this end-to-end governance contract."""
    services = get_app_services(app)
    executed = False

    async def write_note(call: ToolCall, actor: RequestActor) -> ToolResult:
        nonlocal executed
        del actor
        executed = True
        return ToolResult(tool_id=call.tool_id, status="succeeded")

    tool_id = "querymind_connector_review_write_note"
    services.tool_registry.register(ToolDefinition(tool_id=tool_id, operation="write"), write_note)
    actor = RequestActor(user_id="approval-user")
    call = ToolCall(tool_id=tool_id)
    pending = await services.gateway.invoke(call, actor)

    response = TestClient(app).post(
        f"/api/v1/connectors/approvals/{pending.approval_token}",
        json={"confirmed": True},
        headers=HEADERS,
    )

    assert response.status_code == 200
    assert response.json() == {"approval_status": "approved"}
    assert executed is False
    approved = await services.gateway.invoke(
        call.model_copy(update={"approval_token": pending.approval_token}),
        actor,
    )
    assert approved.status == "succeeded"
    assert executed is True


def test_approval_api_rejects_false_confirmation_and_different_actor() -> None:
    """A false confirmation or a different authenticated actor must not approve a token."""
    services = get_app_services(app)
    actor = RequestActor(user_id="approval-user")
    pending = services.approvals.create(ToolCall(tool_id="querymind_connector_review_send"), actor)
    client = TestClient(app)

    false_response = client.post(
        f"/api/v1/connectors/approvals/{pending.token}",
        json={"confirmed": False},
        headers=HEADERS,
    )
    other_response = client.post(
        f"/api/v1/connectors/approvals/{pending.token}",
        json={"confirmed": True},
        headers={**HEADERS, "X-Test-User": "other-user", "X-Test-User-Id": "other-user"},
    )

    assert false_response.status_code == 400
    assert other_response.status_code == 404
    assert services.approvals.consume(
        ToolCall(tool_id="querymind_connector_review_send", approval_token=pending.token),
        actor,
    ) is None


@pytest.mark.parametrize("invalid_state", ["expired", "consumed"])
def test_approval_api_rejects_expired_or_consumed_token(invalid_state: str) -> None:
    """Expired and consumed one-time approvals must never become valid again."""
    services = get_app_services(app)
    actor = RequestActor(user_id="approval-user")
    call = ToolCall(tool_id="querymind_connector_review_charge")
    pending = services.approvals.create(call, actor)
    if invalid_state == "expired":
        services.approvals._requests[pending.token] = pending.model_copy(
            update={"expires_at": datetime.now(UTC) - timedelta(seconds=1)}
        )
    else:
        services.approvals.approve(pending.token, actor)
        assert services.approvals.consume(call.model_copy(update={"approval_token": pending.token}), actor)

    response = TestClient(app).post(
        f"/api/v1/connectors/approvals/{pending.token}",
        json={"confirmed": True},
        headers=HEADERS,
    )

    assert response.status_code == 404


def test_approval_api_fails_closed_when_runtime_dependency_is_missing() -> None:
    """A router mounted without the production dependency container must not silently succeed."""
    isolated = FastAPI()
    isolated.include_router(router)

    response = TestClient(isolated).post(
        "/api/v1/connectors/approvals/unknown-token",
        json={"confirmed": True},
        headers=HEADERS,
    )

    assert response.status_code == 503
