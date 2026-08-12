"""Validation tests for connector configuration contracts."""

import pytest
from pydantic import ValidationError

from app.mcp.contracts import ConnectorDefinition


def test_connector_definition_rejects_an_allowlist_that_normalizes_to_empty() -> None:
    """Whitespace-only host entries must not silently turn the URL policy into an empty set."""
    with pytest.raises(ValidationError, match="allowed_hosts"):
        ConnectorDefinition(
            connector_id="crm",
            owner_id="org-a",
            base_url="https://api.example.com",
            allowed_hosts=frozenset({"   "}),
        )


@pytest.mark.parametrize(
    "allowed_hosts",
    [
        frozenset({"a" * 254}),
        frozenset(f"host-{index}.example" for index in range(21)),
    ],
)
def test_connector_definition_rejects_oversized_allowlist_members_or_counts(allowed_hosts: frozenset[str]) -> None:
    """Service callers cannot bypass the API's finite host boundary."""
    with pytest.raises(ValidationError, match="allowed_hosts"):
        ConnectorDefinition(
            connector_id="crm",
            owner_id="org-a",
            base_url="https://api.example.com",
            allowed_hosts=allowed_hosts,
        )
