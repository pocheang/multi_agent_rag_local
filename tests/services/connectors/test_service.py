"""Tests encrypted, owner-isolated connector credentials."""

import pytest

from app.services.connectors.repository import CredentialRepository
from app.services.connectors.service import ConnectorCredentialService


def test_connector_credentials_are_encrypted_redacted_and_owner_isolated() -> None:
    """Storing plaintext or allowing another owner to resolve it would expose a secret."""
    service = ConnectorCredentialService(CredentialRepository(), encryption_key=b"connector-test-key")

    stored = service.store(connector_id="crm", owner_id="org-a", secret="secret-token-1234")

    assert not hasattr(stored, "encrypted_secret")
    assert stored.display_value.endswith("1234")
    assert service.resolve(stored.credential_id, owner_id="org-a") == "secret-token-1234"

    with pytest.raises(PermissionError):
        service.resolve(stored.credential_id, owner_id="org-b")
