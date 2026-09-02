"""Encrypted connector credentials, persisted to the application database.

Held in a process-local dict until 2026-08-30. A restart threw the secrets away
while `connector_metadata` still pointed at them, so a connector could survive
its own credential and every call through it would fail an owner check it could
never pass again.

The stored value is ciphertext -- `ConnectorCredentialService` encrypts before
handing a record here and this class has no plaintext accessor -- so persisting
it does not widen what a database read exposes. It does mean the encryption key
now has to outlive the process too: with `API_SETTINGS_ENCRYPTION_KEY` rotated
or regenerated, stored credentials become undecryptable rather than merely
absent.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.core.config import get_settings
from app.mcp.contracts import ConnectorCredential


class CredentialRepository:
    """Persist encrypted credentials without a plaintext accessor."""

    def __init__(self, db_path: Path | None = None) -> None:
        self.db_path = db_path or get_settings().app_db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS connector_credentials (
                  credential_id TEXT PRIMARY KEY,
                  connector_id TEXT NOT NULL,
                  owner_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                  encrypted_secret TEXT NOT NULL,
                  display_value TEXT NOT NULL
                )
                """
            )
            conn.execute(
                "CREATE INDEX IF NOT EXISTS idx_connector_credentials_owner ON connector_credentials(owner_id)"
            )

    def save(self, credential: ConnectorCredential) -> ConnectorCredential:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO connector_credentials
                  (credential_id, connector_id, owner_id, encrypted_secret, display_value)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(credential_id) DO UPDATE SET
                  connector_id = excluded.connector_id,
                  owner_id = excluded.owner_id,
                  encrypted_secret = excluded.encrypted_secret,
                  display_value = excluded.display_value
                """,
                (
                    credential.credential_id,
                    credential.connector_id,
                    credential.owner_id,
                    credential.encrypted_secret,
                    credential.display_value,
                ),
            )
        return credential

    def get_for_owner(self, credential_id: str, owner_id: str) -> ConnectorCredential | None:
        """Filter by owner in the query, so a wrong id cannot return a row at all."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM connector_credentials WHERE credential_id = ? AND owner_id = ?",
                (credential_id, owner_id),
            ).fetchone()
        if row is None:
            return None
        return ConnectorCredential(
            credential_id=row["credential_id"],
            connector_id=row["connector_id"],
            owner_id=row["owner_id"],
            encrypted_secret=row["encrypted_secret"],
            display_value=row["display_value"],
        )
