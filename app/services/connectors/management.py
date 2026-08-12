"""Owner-scoped connector metadata, credential, and reachability management."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from urllib.parse import urlparse

import httpx

from app.mcp.contracts import ConnectorDefinition
from app.services.connectors.contracts import ConnectorMetadata, ConnectorProbeResult, ConnectorView
from app.services.connectors.metadata_repository import ConnectorMetadataRepository
from app.services.connectors.service import ConnectorCredentialService
from app.services.security.network import OutboundURLValidationError, validate_public_http_url

ConnectorProbe = Callable[[str, frozenset[str]], Awaitable[ConnectorProbeResult]]


class ConnectorManagementService:
    """Manage non-secret metadata while delegating secrets to the Task 3 credential service."""

    def __init__(
        self,
        repository: ConnectorMetadataRepository,
        credentials: ConnectorCredentialService,
        *,
        probe: ConnectorProbe,
    ) -> None:
        self._repository = repository
        self._credentials = credentials
        self._probe = probe

    def create(
        self,
        *,
        connector_id: str,
        owner_id: str,
        name: str,
        base_url: str,
        allowed_hosts: frozenset[str],
        secret: str,
    ) -> ConnectorView:
        if self._repository.get(connector_id, owner_id) is not None:
            raise ValueError("connector already exists")
        definition = ConnectorDefinition(
            connector_id=connector_id,
            owner_id=owner_id,
            base_url=base_url,
            allowed_hosts=allowed_hosts,
        )
        normalized_url = validate_public_http_url(str(definition.base_url))
        for allowed_host in definition.allowed_hosts:
            validate_public_http_url(f"https://{allowed_host}")
        host = (urlparse(normalized_url).hostname or "").lower()
        if host not in definition.allowed_hosts:
            raise ValueError("base_url host must be present in allowed_hosts")
        credential = self._credentials.store(connector_id=connector_id, owner_id=owner_id, secret=secret)
        metadata = self._repository.create(
            ConnectorMetadata(
                connector_id=connector_id,
                owner_id=owner_id,
                name=name.strip(),
                base_url=definition.base_url,
                allowed_hosts=definition.allowed_hosts,
                credential_id=credential.credential_id,
                credential_display=credential.display_value,
            )
        )
        return ConnectorView.from_metadata(metadata)

    def list_for_owner(self, owner_id: str) -> tuple[ConnectorView, ...]:
        return tuple(ConnectorView.from_metadata(item) for item in self._repository.list_for_owner(owner_id))

    def disable(self, connector_id: str, owner_id: str) -> ConnectorView:
        metadata = self._require(connector_id, owner_id)
        disabled = self._repository.replace(metadata.model_copy(update={"status": "disabled"}))
        return ConnectorView.from_metadata(disabled)

    def enable(self, connector_id: str, owner_id: str) -> ConnectorView:
        metadata = self._require(connector_id, owner_id)
        enabled = self._repository.replace(metadata.model_copy(update={"status": "enabled"}))
        return ConnectorView.from_metadata(enabled)

    async def test(self, connector_id: str, owner_id: str) -> ConnectorProbeResult:
        metadata = self._require(connector_id, owner_id)
        if metadata.status != "enabled":
            raise ValueError("disabled connectors cannot be tested")
        self._credentials.resolve(metadata.credential_id, owner_id=owner_id)
        result = await self._probe(str(metadata.base_url), metadata.allowed_hosts)
        self._repository.replace(metadata.model_copy(update={"test_status": result.status}))
        return result

    def _require(self, connector_id: str, owner_id: str) -> ConnectorMetadata:
        metadata = self._repository.get(connector_id, owner_id)
        if metadata is None:
            raise KeyError(connector_id)
        return metadata


async def probe_http_connector(base_url: str, allowed_hosts: frozenset[str]) -> ConnectorProbeResult:
    """Perform one bounded, read-only HTTP reachability probe without redirects."""
    try:
        safe_url = validate_public_http_url(base_url)
        async with httpx.AsyncClient(follow_redirects=False, timeout=5.0) as client:
            response = await client.get(safe_url)
        final_host = (urlparse(str(response.url)).hostname or "").lower()
        if final_host not in allowed_hosts:
            return ConnectorProbeResult(status="failed", message="response host is not allowed")
        if 200 <= response.status_code < 400:
            return ConnectorProbeResult(status="passed", message="reachable")
        return ConnectorProbeResult(status="failed", message=f"HTTP {response.status_code}")
    except OutboundURLValidationError:
        return ConnectorProbeResult(status="failed", message="probe blocked by network boundary policy")
    except Exception as exc:
        return ConnectorProbeResult(status="failed", message=f"probe failed: {type(exc).__name__}")
