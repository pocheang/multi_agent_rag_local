"""Thread-safe in-memory repository for owner-scoped connector metadata."""

from __future__ import annotations

from threading import RLock

from app.services.connectors.contracts import ConnectorMetadata


class ConnectorMetadataRepository:
    """Store connector metadata without co-locating or exposing credentials."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str], ConnectorMetadata] = {}
        self._lock = RLock()

    def create(self, metadata: ConnectorMetadata) -> ConnectorMetadata:
        key = (metadata.owner_id, metadata.connector_id)
        with self._lock:
            if key in self._records:
                raise ValueError("connector already exists")
            self._records[key] = metadata
        return metadata

    def get(self, connector_id: str, owner_id: str) -> ConnectorMetadata | None:
        with self._lock:
            return self._records.get((owner_id, connector_id))

    def list_for_owner(self, owner_id: str) -> tuple[ConnectorMetadata, ...]:
        with self._lock:
            records = tuple(record for (owner, _), record in self._records.items() if owner == owner_id)
        return tuple(sorted(records, key=lambda record: record.connector_id))

    def replace(self, metadata: ConnectorMetadata) -> ConnectorMetadata:
        key = (metadata.owner_id, metadata.connector_id)
        with self._lock:
            if key not in self._records:
                raise KeyError(metadata.connector_id)
            self._records[key] = metadata
        return metadata
