"""Redirect safety tests for REST connector requests."""

import pytest

from app.mcp.connectors.rest import RestConnector
from app.mcp.contracts import ConnectorDefinition, RestRequest, RestResponse, ToolArgument, ToolCall
from app.orchestration.request import RequestActor


@pytest.mark.asyncio
async def test_rest_connector_disables_redirects_and_rejects_an_untrusted_final_url() -> None:
    """A redirect must neither silently leave the allowlist nor be returned as success."""
    requests: list[RestRequest] = []

    async def transport(request: RestRequest) -> RestResponse:
        requests.append(request)
        return RestResponse(final_url="https://evil.example/records", body="unexpected redirect body")

    connector = RestConnector(
        ConnectorDefinition(
            connector_id="crm",
            owner_id="org-a",
            base_url="https://api.example.com/v1",
            allowed_hosts=frozenset({"api.example.com"}),
        ),
        transport=transport,
    )

    result = await connector.invoke(
        ToolCall(
            tool_id="querymind_connector_read_records",
            arguments=(ToolArgument(name="path", value="/records"),),
        ),
        RequestActor(user_id="user-1"),
    )

    assert requests[0].follow_redirects is False
    assert result.status == "failed"
    assert result.summary == "connector host is not allowed"
