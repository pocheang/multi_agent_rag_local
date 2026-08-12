"""Bounds for Task 4 browser and SSE contracts."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.api.routes.connectors import ConnectorCreateRequest, ConnectorListResponse
from app.api.runtime import get_connector_service
from app.domain.events import EventMetadata, ExecutionEvent
from app.main import app
from app.services.connectors.contracts import ConnectorView


def _connector_view() -> ConnectorView:
    return ConnectorView(
        connector_id="crm",
        name="CRM",
        base_url="https://api.example.com/v1",
        allowed_hosts=("api.example.com",),
        status="enabled",
        test_status="not_tested",
    )


@pytest.mark.parametrize(
    "factory",
    [
        lambda: EventMetadata(key="k" * 65, value="value"),
        lambda: EventMetadata(key="key", value="v" * 1_001),
        lambda: ExecutionEvent(stage="tool", status="skipped", message="m" * 1_001),
        lambda: ExecutionEvent(
            stage="tool",
            status="skipped",
            metadata=tuple(EventMetadata(key=f"key-{index}", value="value") for index in range(21)),
        ),
    ],
)
def test_execution_event_rejects_oversized_cross_layer_values(factory: object) -> None:
    """Trace metadata and messages must have finite browser-safe limits."""
    with pytest.raises(ValidationError):
        factory()


@pytest.mark.parametrize(
    "factory",
    [
        lambda: ConnectorCreateRequest(
            connector_id="crm",
            name="CRM",
            base_url=f"https://api.example.com/{'x' * 2_025}",
            allowed_hosts=frozenset({"api.example.com"}),
            secret="secret",
        ),
        lambda: ConnectorCreateRequest(
            connector_id="crm",
            name="CRM",
            base_url="https://api.example.com",
            allowed_hosts=frozenset({"a" * 254}),
            secret="secret",
        ),
        lambda: ConnectorView(
            connector_id="c" * 65,
            name="N" * 121,
            base_url="https://api.example.com",
            allowed_hosts=tuple(f"host-{index}.example" for index in range(21)),
            status="enabled",
            test_status="not_tested",
        ),
        lambda: ConnectorListResponse(connectors=tuple(_connector_view() for _ in range(101))),
    ],
)
def test_connector_boundary_models_reject_oversized_urls_hosts_and_views(factory: object) -> None:
    """Connector request and response collections must not accept unbounded browser payloads."""
    with pytest.raises(ValidationError):
        factory()


def test_task4_path_inputs_reject_oversized_tokens_and_execution_ids() -> None:
    """Path parameters must be bounded before approval or trace lookup occurs."""
    headers = {
        "X-Test-User": "boundary-user",
        "X-Test-Role": "viewer",
        "X-Test-User-Id": "boundary-user",
    }
    client = TestClient(app)

    approval_response = client.post(
        f"/api/v1/connectors/approvals/{'x' * 257}",
        headers=headers,
        json={"confirmed": True},
    )
    trace_response = client.get(
        f"/api/v1/orchestration/executions/{uuid4().hex * 5}/events",
        headers=headers,
    )

    assert approval_response.status_code == 422
    assert trace_response.status_code == 422


@pytest.mark.parametrize(("connector_id"), ["x" * 65, "Invalid.connector"])
@pytest.mark.parametrize("action", ["disable", "enable", "test"])
def test_connector_actions_reject_invalid_path_ids_before_service_lookup(
    connector_id: str,
    action: str,
) -> None:
    """Connector action IDs must be validated before an owner-scoped lookup."""
    looked_up: list[str] = []

    class LookupGuard:
        def disable(self, connector_id: str, owner_id: str) -> None:
            looked_up.append(connector_id)

        def enable(self, connector_id: str, owner_id: str) -> None:
            looked_up.append(connector_id)

        async def test(self, connector_id: str, owner_id: str) -> None:
            looked_up.append(connector_id)

    app.dependency_overrides[get_connector_service] = LookupGuard
    try:
        response = TestClient(app).post(
            f"/api/v1/connectors/{connector_id}/{action}",
            headers={
                "X-Test-User": "boundary-user",
                "X-Test-Role": "viewer",
                "X-Test-User-Id": "boundary-user",
            },
        )
    finally:
        app.dependency_overrides.pop(get_connector_service, None)

    assert response.status_code == 422
    assert looked_up == []
