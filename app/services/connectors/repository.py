"""Credential repository interface with an in-memory implementation."""

from __future__ import annotations

from app.mcp.contracts import ConnectorCredential


class CredentialRepository:
    """Persist encrypted credentials without a plaintext accessor."""

    def __init__(self) -> None:
        self._records: dict[str, ConnectorCredential] = {}

    def save(self, credential: ConnectorCredential) -> ConnectorCredential:
        self._records[credential.credential_id] = credential
        return credential

    def get_for_owner(self, credential_id: str, owner_id: str) -> ConnectorCredential | None:
        credential = self._records.get(credential_id)
        if credential is None or credential.owner_id != owner_id:
            return None
        return credential
