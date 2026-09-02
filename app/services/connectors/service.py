"""Encrypted connector credential lifecycle service."""

from __future__ import annotations

from app.mcp.contracts import ConnectorCredential, ConnectorCredentialDisplay
from app.services.auth.encryption import decrypt_secret_text, encrypt_secret_text
from app.services.connectors.repository import CredentialRepository


class ConnectorCredentialService:
    """Encrypt once on storage and resolve only for the credential owner."""

    def __init__(self, repository: CredentialRepository, *, encryption_key: bytes) -> None:
        if not encryption_key:
            raise ValueError("connector credential encryption key is required")
        self._repository = repository
        self._encryption_key = encryption_key

    def store(self, *, connector_id: str, owner_id: str, secret: str) -> ConnectorCredentialDisplay:
        """Persist a secret and return only a redacted credential display contract."""
        normalized_secret = secret.strip()
        if not normalized_secret:
            raise ValueError("connector credential secret must not be blank")
        credential = ConnectorCredential(
            connector_id=connector_id,
            owner_id=owner_id,
            encrypted_secret=encrypt_secret_text(normalized_secret, self._encryption_key),
            display_value=_redact(normalized_secret),
        )
        stored = self._repository.save(credential)
        return ConnectorCredentialDisplay(
            credential_id=stored.credential_id,
            connector_id=stored.connector_id,
            display_value=stored.display_value,
        )

    def resolve(self, credential_id: str, *, owner_id: str) -> str:
        """Resolve plaintext internally only after an owner check."""
        credential = self._repository.get_for_owner(credential_id, owner_id)
        if credential is None:
            raise PermissionError("connector credential is not available to this owner")
        return decrypt_secret_text(credential.encrypted_secret, self._encryption_key)


def _redact(secret: str) -> str:
    suffix = secret[-4:] if len(secret) >= 4 else "*" * len(secret)
    return f"••••{suffix}"
