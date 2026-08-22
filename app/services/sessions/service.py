"""
Unified interface for session metadata service with configurable backend.

Automatically selects between memory and database backends based on configuration.
"""

from __future__ import annotations

import hashlib

from app.core.config import get_settings
from app.services.sessions.metadata import (
    MetadataUpdate,
    SessionCategory,
    SessionMetadata,
    TagExtractor,
)
from app.services.sessions.metadata import (
    SessionMetadataService as MemoryService,
)

__all__ = [
    "SessionMetadata",
    "SessionCategory",
    "MetadataUpdate",
    "TagExtractor",
    "get_metadata_service",
]


def get_metadata_service(user_id: str | None = None):
    """
    Get metadata service instance based on configuration.

    Backend selection (SESSION_METADATA_BACKEND):
    - "memory": In-memory storage (fast, volatile)
    - "database": SQLite storage (persistent, production-ready)

    Returns:
        Metadata service instance (memory or database backend)
    """
    settings = get_settings()
    backend = getattr(settings, "session_metadata_backend", "database").lower()

    if backend == "database":
        # Import here to avoid circular dependency
        from app.services.sessions.metadata_db import get_metadata_db

        if user_id:
            namespace = hashlib.sha256(str(user_id).encode("utf-8")).hexdigest()
            db_path = settings.sessions_path / "metadata" / f"{namespace}.db"
            return get_metadata_db(db_path)
        return get_metadata_db()
    else:
        # Default to memory backend
        return _get_memory_service(user_id)


# ============================================================================
# Memory Backend Singleton
# ============================================================================

_memory_service_instances: dict[str, MemoryService] = {}


def _get_memory_service(user_id: str | None = None) -> MemoryService:
    """Get singleton instance of memory-backed service."""
    namespace = str(user_id or "__legacy__")
    if namespace not in _memory_service_instances:
        _memory_service_instances[namespace] = MemoryService()
    return _memory_service_instances[namespace]
