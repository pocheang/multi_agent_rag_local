"""Bounded connector-management contracts safe across service boundaries."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, HttpUrl

from app.domain.contracts import ImmutableContract

ConnectorStatus = Literal["enabled", "disabled"]
ConnectorTestStatus = Literal["not_tested", "passed", "failed"]
ConnectorURL = Annotated[HttpUrl, Field(max_length=2_048)]
ConnectorHost = Annotated[str, Field(min_length=1, max_length=253)]


class ConnectorMetadata(ImmutableContract):
    """Internal connector metadata; credentials remain separate and encrypted."""

    connector_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    owner_id: str = Field(min_length=1, max_length=128)
    name: str = Field(min_length=1, max_length=120)
    base_url: ConnectorURL
    allowed_hosts: frozenset[ConnectorHost] = Field(min_length=1, max_length=20)
    credential_id: str = Field(min_length=1, max_length=128)
    credential_display: str = Field(min_length=3, max_length=32)
    status: ConnectorStatus = "enabled"
    test_status: ConnectorTestStatus = "not_tested"


class ConnectorView(ImmutableContract):
    """Only non-credential connector metadata that may be returned to a browser."""

    connector_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    name: str = Field(min_length=1, max_length=120)
    base_url: ConnectorURL
    allowed_hosts: tuple[ConnectorHost, ...] = Field(min_length=1, max_length=20)
    status: ConnectorStatus
    test_status: ConnectorTestStatus

    @classmethod
    def from_metadata(cls, metadata: ConnectorMetadata) -> ConnectorView:
        return cls(
            connector_id=metadata.connector_id,
            name=metadata.name,
            base_url=metadata.base_url,
            allowed_hosts=tuple(sorted(metadata.allowed_hosts)),
            status=metadata.status,
            test_status=metadata.test_status,
        )


class ConnectorProbeResult(ImmutableContract):
    """Safe result of one read-only connector reachability probe."""

    status: Literal["passed", "failed"]
    message: str = Field(min_length=1, max_length=200)
