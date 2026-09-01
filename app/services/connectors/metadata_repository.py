"""Owner-scoped connector metadata, persisted to the application database.

This was a process-local dict until 2026-08-30, which was survivable only while
the governed tool path could not execute anything: a restart silently emptied
every user's integrations, and the connector a user configured on one worker was
invisible to the next. Now that a chat request can actually disable a connector,
"it exists" has to outlive the process that heard about it.

Follows the store pattern the rest of the app uses -- own connection per call,
schema created on construction -- rather than a shared pool, which this codebase
deliberately does not have (see CLAUDE.md, Technology Stack).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.core.config import get_settings
from app.services.connectors.contracts import ConnectorMetadata


class ConnectorMetadataRepository:
    """Store connector metadata without co-locating or exposing credentials."""

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
                CREATE TABLE IF NOT EXISTS connector_metadata (
                  owner_id TEXT NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
                  connector_id TEXT NOT NULL,
                  name TEXT NOT NULL,
                  base_url TEXT NOT NULL,
                  allowed_hosts TEXT NOT NULL,
                  credential_id TEXT NOT NULL,
                  credential_display TEXT NOT NULL,
                  status TEXT NOT NULL,
                  test_status TEXT NOT NULL,
                  PRIMARY KEY (owner_id, connector_id)
                )
                """
            )

    def create(self, metadata: ConnectorMetadata) -> ConnectorMetadata:
        """Insert, letting the primary key decide whether it already exists.

        The dict version read, compared, then wrote under a lock, which only
        made the race single-process. The unique constraint settles it for good.
        """
        try:
            with self._connect() as conn:
                conn.execute(
                    """
                    INSERT INTO connector_metadata
                      (owner_id, connector_id, name, base_url, allowed_hosts,
                       credential_id, credential_display, status, test_status)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    _to_row(metadata),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("connector already exists") from exc
        return metadata

    def get(self, connector_id: str, owner_id: str) -> ConnectorMetadata | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM connector_metadata WHERE owner_id = ? AND connector_id = ?",
                (owner_id, connector_id),
            ).fetchone()
        return None if row is None else _from_row(row)

    def list_for_owner(self, owner_id: str) -> tuple[ConnectorMetadata, ...]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM connector_metadata WHERE owner_id = ? ORDER BY connector_id",
                (owner_id,),
            ).fetchall()
        return tuple(_from_row(row) for row in rows)

    def replace(self, metadata: ConnectorMetadata) -> ConnectorMetadata:
        with self._connect() as conn:
            updated = conn.execute(
                """
                UPDATE connector_metadata
                   SET name = ?, base_url = ?, allowed_hosts = ?, credential_id = ?,
                       credential_display = ?, status = ?, test_status = ?
                 WHERE owner_id = ? AND connector_id = ?
                """,
                (
                    metadata.name,
                    str(metadata.base_url),
                    json.dumps(sorted(metadata.allowed_hosts)),
                    metadata.credential_id,
                    metadata.credential_display,
                    metadata.status,
                    metadata.test_status,
                    metadata.owner_id,
                    metadata.connector_id,
                ),
            ).rowcount
        if not updated:
            raise KeyError(metadata.connector_id)
        return metadata


def _to_row(metadata: ConnectorMetadata) -> tuple[str, ...]:
    return (
        metadata.owner_id,
        metadata.connector_id,
        metadata.name,
        str(metadata.base_url),
        json.dumps(sorted(metadata.allowed_hosts)),
        metadata.credential_id,
        metadata.credential_display,
        metadata.status,
        metadata.test_status,
    )


def _from_row(row: sqlite3.Row) -> ConnectorMetadata:
    return ConnectorMetadata(
        connector_id=row["connector_id"],
        owner_id=row["owner_id"],
        name=row["name"],
        base_url=row["base_url"],
        allowed_hosts=frozenset(json.loads(row["allowed_hosts"])),
        credential_id=row["credential_id"],
        credential_display=row["credential_display"],
        status=row["status"],
        test_status=row["test_status"],
    )
