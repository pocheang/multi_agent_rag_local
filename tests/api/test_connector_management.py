"""API contracts for owner-scoped connector metadata management."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.runtime import get_connector_service
from app.main import app
from app.services.connectors.contracts import ConnectorProbeResult
from app.services.connectors.management import ConnectorManagementService
from app.services.connectors.metadata_repository import ConnectorMetadataRepository
from app.services.connectors.repository import CredentialRepository
from app.services.connectors.service import ConnectorCredentialService


def _headers(user_id: str) -> dict[str, str]:
    return {
        "X-Test-User": user_id,
        "X-Test-Role": "viewer",
        "X-Test-User-Id": user_id,
    }


def test_connector_management_is_owner_scoped_reversible_and_returns_no_credential_display() -> None:
    """Cross-owner access, irreversible disable, or any credential display must fail this contract."""
    owner_id = f"connector-owner-{uuid4().hex}"
    other_id = f"connector-other-{uuid4().hex}"
    connector_id = f"crm-{uuid4().hex[:8]}"
    client = TestClient(app)
    secret = "server-secret-9876"

    created = client.post(
        "/api/v1/connectors",
        headers=_headers(owner_id),
        json={
            "connector_id": connector_id,
            "name": "Sales CRM",
            "base_url": "https://api.example.com/v1",
            "allowed_hosts": ["api.example.com"],
            "secret": secret,
        },
    )

    assert created.status_code == 201
    payload = created.json()
    assert payload == {
        "connector_id": connector_id,
        "name": "Sales CRM",
        "base_url": "https://api.example.com/v1",
        "allowed_hosts": ["api.example.com"],
        "status": "enabled",
        "test_status": "not_tested",
    }
    assert secret not in created.text
    assert "encrypted_secret" not in created.text

    own_list = client.get("/api/v1/connectors", headers=_headers(owner_id))
    other_list = client.get("/api/v1/connectors", headers=_headers(other_id))

    assert own_list.status_code == 200
    assert own_list.json() == {"connectors": [payload]}
    assert other_list.json() == {"connectors": []}

    denied = client.post(
        f"/api/v1/connectors/{connector_id}/disable",
        headers=_headers(other_id),
    )
    disabled = client.post(
        f"/api/v1/connectors/{connector_id}/disable",
        headers=_headers(owner_id),
    )

    assert denied.status_code == 404
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"

    re_enabled = client.post(
        f"/api/v1/connectors/{connector_id}/enable",
        headers=_headers(owner_id),
    )

    assert re_enabled.status_code == 200
    assert re_enabled.json()["status"] == "enabled"
    assert "credential" not in re_enabled.text.lower()


def test_connector_test_endpoint_returns_the_real_service_probe_result() -> None:
    """Returning a manufactured success without invoking the configured probe must fail."""
    owner_id = f"probe-owner-{uuid4().hex}"
    connector_id = f"probe-{uuid4().hex[:8]}"
    probed: list[str] = []

    async def probe(base_url: str, allowed_hosts: frozenset[str]):
        assert allowed_hosts == frozenset({"api.example.com"})
        probed.append(base_url)
        return ConnectorProbeResult(status="passed", message="reachable")

    service = ConnectorManagementService(
        ConnectorMetadataRepository(),
        ConnectorCredentialService(CredentialRepository(), encryption_key=b"connector-api-test-key"),
        probe=probe,
    )
    app.dependency_overrides[get_connector_service] = lambda: service
    client = TestClient(app)
    created = client.post(
        "/api/v1/connectors",
        headers=_headers(owner_id),
        json={
            "connector_id": connector_id,
            "name": "Probe target",
            "base_url": "https://api.example.com/health",
            "allowed_hosts": ["api.example.com"],
            "secret": "probe-secret",
        },
    )
    assert created.status_code == 201

    try:
        response = client.post(
            f"/api/v1/connectors/{connector_id}/test",
            headers=_headers(owner_id),
        )
    finally:
        app.dependency_overrides.pop(get_connector_service, None)

    assert response.status_code == 200
    assert response.json() == {"status": "passed", "message": "reachable"}
    assert probed == ["https://api.example.com/health"]


@pytest.mark.parametrize(
    ("base_url", "allowed_host"),
    [
        ("http://127.0.0.1/admin", "127.0.0.1"),
        ("http://10.0.0.8/admin", "10.0.0.8"),
        ("http://169.254.169.254/latest/meta-data", "169.254.169.254"),
        ("http://0.0.0.0/admin", "0.0.0.0"),
        ("http://localhost/admin", "localhost"),
    ],
)
def test_connector_create_rejects_caller_allowlisted_non_public_targets(
    base_url: str,
    allowed_host: str,
) -> None:
    """A caller-controlled allowlist must never authorize server-side requests to non-public networks."""
    connector_id = f"blocked-{uuid4().hex[:8]}"

    response = TestClient(app).post(
        "/api/v1/connectors",
        headers=_headers(f"blocked-owner-{uuid4().hex}"),
        json={
            "connector_id": connector_id,
            "name": "Blocked target",
            "base_url": base_url,
            "allowed_hosts": [allowed_host],
            "secret": "must-not-be-stored",
        },
    )

    assert response.status_code == 400
    assert "blocked" in response.json()["detail"].lower()


def test_connector_create_rejects_hostname_resolving_to_private_address(monkeypatch: pytest.MonkeyPatch) -> None:
    """A public-looking hostname resolving only to RFC1918 space must be rejected server-side."""
    monkeypatch.setattr(
        "app.services.network_security.socket.getaddrinfo",
        lambda *_args, **_kwargs: [(2, 1, 6, "", ("10.10.0.5", 443))],
    )

    response = TestClient(app).post(
        "/api/v1/connectors",
        headers=_headers(f"dns-owner-{uuid4().hex}"),
        json={
            "connector_id": f"dns-{uuid4().hex[:8]}",
            "name": "DNS rebinding target",
            "base_url": "https://internal.example/health",
            "allowed_hosts": ["internal.example"],
            "secret": "must-not-be-stored",
        },
    )

    assert response.status_code == 400
    assert "blocked" in response.json()["detail"].lower()


@pytest.mark.parametrize(
    "unsafe_secondary_host",
    [
        "localhost",
        "127.0.0.1",
        "10.0.0.8",
        "169.254.169.254",
        "240.0.0.1",
        "0.0.0.0",
    ],
)
def test_connector_create_rejects_non_public_secondary_allowed_hosts(unsafe_secondary_host: str) -> None:
    """Every persisted allowlist entry must be public, not only the base URL host."""
    owner_id = f"secondary-owner-{uuid4().hex}"
    connector_id = f"secondary-{uuid4().hex[:8]}"
    client = TestClient(app)

    response = client.post(
        "/api/v1/connectors",
        headers=_headers(owner_id),
        json={
            "connector_id": connector_id,
            "name": "Public base with unsafe secondary host",
            "base_url": "https://93.184.216.34/v1",
            "allowed_hosts": ["93.184.216.34", unsafe_secondary_host],
            "secret": "must-not-be-stored",
        },
    )

    assert response.status_code == 400
    assert "blocked" in response.json()["detail"].lower()
    assert client.get("/api/v1/connectors", headers=_headers(owner_id)).json() == {"connectors": []}


def test_connector_create_rejects_secondary_hostname_resolving_to_private_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An extra allowlist hostname must undergo the same DNS safety check before persistence."""

    def resolve(host: str, port: int, **_kwargs: object):
        address = "10.10.0.5" if host == "secondary.example" else "93.184.216.34"
        return [(2, 1, 6, "", (address, port))]

    monkeypatch.setattr("app.services.network_security.socket.getaddrinfo", resolve)
    owner_id = f"secondary-dns-owner-{uuid4().hex}"
    client = TestClient(app)

    response = client.post(
        "/api/v1/connectors",
        headers=_headers(owner_id),
        json={
            "connector_id": f"secondary-dns-{uuid4().hex[:8]}",
            "name": "Public base with private secondary DNS",
            "base_url": "https://93.184.216.34/v1",
            "allowed_hosts": ["93.184.216.34", "secondary.example"],
            "secret": "must-not-be-stored",
        },
    )

    assert response.status_code == 400
    assert "blocked" in response.json()["detail"].lower()
