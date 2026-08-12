"""Tests URL allowlist enforcement for read-only REST connectors."""

import pytest

from app.mcp.connectors.rest import RestConnector
from app.mcp.contracts import ConnectorDefinition, RestRequest, RestResponse, ToolArgument, ToolCall
from app.orchestration.request import RequestActor


@pytest.mark.asyncio
async def test_rest_connector_rejects_open_world_url_before_transport() -> None:
    """Allowing an absolute attacker URL would bypass the configured connector allowlist."""
    requests: list[str] = []

    async def transport(request: RestRequest) -> RestResponse:
        requests.append(str(request.url))
        return RestResponse(final_url=request.url, body="ok")

    connector = RestConnector(
        ConnectorDefinition(
            connector_id="crm",
            owner_id="org-a",
            base_url="https://api.example.com/v1",
            allowed_hosts=frozenset({"api.example.com"}),
        ),
        transport=transport,
    )
    call = ToolCall(
        tool_id="querymind_connector_read_records",
        arguments=(ToolArgument(name="path", value="https://evil.example/steal"),),
    )

    result = await connector.invoke(call, RequestActor(user_id="user-1"))

    assert result.status == "failed"
    assert requests == []
