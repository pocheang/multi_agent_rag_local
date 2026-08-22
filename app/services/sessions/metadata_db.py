"""
Database models and persistence layer for session metadata.

Provides SQLite-backed storage with LRU cache for performance.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.services.sessions.metadata import (
    MAX_SESSIONS,
    MetadataUpdate,
    SessionCategory,
    SessionMetadata,
    normalize_description,
    normalize_tags,
)

__all__ = [
    "SessionMetadataDB",
    "get_metadata_db",
]

logger = logging.getLogger(__name__)


# ============================================================================
# Database Schema
# ============================================================================

CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS session_metadata (
    session_id TEXT PRIMARY KEY,
    tags TEXT NOT NULL,  -- JSON array
    category TEXT,
    description TEXT,
    auto_tags TEXT NOT NULL,  -- JSON array
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    query_count INTEGER NOT NULL DEFAULT 0,
    last_query_at TEXT
)
"""

CREATE_INDEXES_SQL = [
    "CREATE INDEX IF NOT EXISTS idx_session_updated_at ON session_metadata(updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_session_category ON session_metadata(category)",
    "CREATE INDEX IF NOT EXISTS idx_session_query_count ON session_metadata(query_count)",
    # 安全修复：添加复合索引以优化常见查询模式
    "CREATE INDEX IF NOT EXISTS idx_session_category_updated ON session_metadata(category, updated_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_session_last_query ON session_metadata(last_query_at DESC) WHERE last_query_at IS NOT NULL",
]


# ============================================================================
# Database-Backed Metadata Service
# ============================================================================


class SessionMetadataDB:
    """
    Database-backed session metadata service with LRU cache.

    Architecture:
    - L1 Cache: OrderedDict (LRU, in-memory, fast reads)
    - L2 Storage: SQLite (persistent, survives restarts)

    Write strategy: Write-through (update both cache and DB)
    Read strategy: Cache-first (check cache, fallback to DB)
    """

    def __init__(self, db_path: Path | None = None, max_cache_size: int = MAX_SESSIONS):
        """
        Initialize database-backed metadata service.

        Args:
            db_path: Path to SQLite database (defaults to querymind.db)
            max_cache_size: Maximum number of sessions in LRU cache
        """
        get_settings()
        self.db_path = db_path or self._get_db_path()
        self.max_cache_size = max_cache_size

        # L1 Cache (LRU)
        self._cache: OrderedDict[str, SessionMetadata] = OrderedDict()

        # Initialize database
        self._init_schema()

    def _get_db_path(self) -> Path:
        """Get database path from settings."""
        settings = get_settings()
        # Parse DATABASE_URL (e.g. "sqlite:///./data/querymind.db")
        db_url = getattr(settings, "database_url", "sqlite:///./data/querymind.db")
        if db_url.startswith("sqlite:///"):
            path_str = db_url[10:]  # Remove "sqlite:///"
            return Path(path_str).resolve()
        else:
            # Fallback
            return Path("./data/querymind.db").resolve()

    def _connect(self) -> sqlite3.Connection:
        """Create database connection."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.db_path, timeout=10.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn

    def _init_schema(self) -> None:
        """Initialize database schema."""
        with self._connect() as conn:
            conn.execute(CREATE_TABLE_SQL)
            for index_sql in CREATE_INDEXES_SQL:
                conn.execute(index_sql)
            conn.commit()

    def _serialize_metadata(self, metadata: SessionMetadata) -> dict[str, Any]:
        """Serialize SessionMetadata to database row."""
        return {
            "session_id": metadata.session_id,
            "tags": json.dumps(metadata.tags),
            "category": metadata.category,
            "description": metadata.description,
            "auto_tags": json.dumps(metadata.auto_tags),
            "created_at": metadata.created_at.isoformat(),
            "updated_at": metadata.updated_at.isoformat(),
            "query_count": metadata.query_count,
            "last_query_at": metadata.last_query_at.isoformat() if metadata.last_query_at else None,
        }

    def _deserialize_row(self, row: sqlite3.Row) -> SessionMetadata:
        """Deserialize database row to SessionMetadata."""
        return SessionMetadata(
            session_id=row["session_id"],
            tags=json.loads(row["tags"]),
            category=row["category"],
            description=row["description"],
            auto_tags=json.loads(row["auto_tags"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            query_count=row["query_count"],
            last_query_at=datetime.fromisoformat(row["last_query_at"]) if row["last_query_at"] else None,
        )

    def _evict_from_cache_if_needed(self) -> None:
        """
        Evict oldest entry from cache if at capacity.

        安全修复：使用 logger 而非 print()
        """
        if len(self._cache) >= self.max_cache_size:
            evicted_id, _ = self._cache.popitem(last=False)
            logger.debug(f"LRU cache evicted session: {evicted_id}")

    def _cache_put(self, metadata: SessionMetadata) -> None:
        """Put metadata in cache (with LRU eviction)."""
        self._evict_from_cache_if_needed()
        self._cache[metadata.session_id] = metadata

    def _cache_touch(self, session_id: str) -> None:
        """Touch cache entry (move to end for LRU)."""
        if session_id in self._cache:
            self._cache.move_to_end(session_id)

    def create(self, metadata: SessionMetadata) -> SessionMetadata:
        """
        Create new session metadata (write-through).

        安全修复：使用 BEGIN IMMEDIATE 防止并发竞态条件

        Args:
            metadata: Metadata to create

        Returns:
            Created metadata

        Raises:
            ValueError: If session already exists
        """
        # 安全修复：使用 BEGIN IMMEDIATE 获取立即写锁，防止竞态条件
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                # Check if exists in DB
                cursor = conn.execute(
                    "SELECT session_id FROM session_metadata WHERE session_id = ?", (metadata.session_id,)
                )
                if cursor.fetchone():
                    raise ValueError(f"Metadata already exists for session {metadata.session_id}")

                # Insert into DB
                row = self._serialize_metadata(metadata)
                conn.execute(
                    """
                    INSERT INTO session_metadata
                    (session_id, tags, category, description, auto_tags, created_at, updated_at, query_count, last_query_at)
                    VALUES (:session_id, :tags, :category, :description, :auto_tags, :created_at, :updated_at, :query_count, :last_query_at)
                    """,
                    row,
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise

        # Update cache
        self._cache_put(metadata)

        return metadata

    def get(self, session_id: str) -> SessionMetadata | None:
        """
        Get session metadata (cache-first).

        Args:
            session_id: Session identifier

        Returns:
            Metadata or None if not found
        """
        # Check cache first
        if session_id in self._cache:
            self._cache_touch(session_id)
            return self._cache[session_id]

        # Fallback to DB
        with self._connect() as conn:
            cursor = conn.execute("SELECT * FROM session_metadata WHERE session_id = ?", (session_id,))
            row = cursor.fetchone()

            if row:
                metadata = self._deserialize_row(row)
                # Warm cache
                self._cache_put(metadata)
                return metadata

        return None

    def get_metadata(self, session_id: str) -> SessionMetadata | None:
        """
        Get session metadata (alias for get).

        Args:
            session_id: Session identifier

        Returns:
            Metadata or None if not found
        """
        return self.get(session_id)

    def create_metadata(
        self,
        session_id: str,
        tags: list[str] | None = None,
        category: SessionCategory | None = None,
        description: str | None = None,
    ) -> SessionMetadata:
        """
        Create new session metadata (alias for create).

        Args:
            session_id: Unique session identifier
            tags: User-defined tags
            category: Session category
            description: Session description

        Returns:
            Created metadata

        Raises:
            ValueError: If session already exists
        """
        metadata = SessionMetadata(
            session_id=session_id,
            tags=normalize_tags(tags or []),
            category=category,
            description=normalize_description(description),
        )
        return self.create(metadata)

    def update_metadata(
        self,
        session_id: str,
        update: MetadataUpdate,
    ) -> SessionMetadata:
        """
        Update existing session metadata (alias for update).

        Args:
            session_id: Session to update
            update: Update specification

        Returns:
            Updated metadata

        Raises:
            KeyError: If session not found
        """
        return self.update(session_id, update)

    def delete_metadata(self, session_id: str) -> bool:
        """
        Delete session metadata (alias for delete).

        Args:
            session_id: Session to delete

        Returns:
            True if deleted, False if not found
        """
        return self.delete(session_id)

    def list_all_metadata(self) -> list[SessionMetadata]:
        """
        List all session metadata (alias for list_all).

        Returns:
            List of all metadata (most recently updated first)
        """
        return self.list_all()

    def extract_and_update_auto_tags(
        self,
        session_id: str,
        messages: list[dict],
        max_tags: int = 5,
    ) -> list[str]:
        """
        Extract automatic tags from messages and update metadata.

        Args:
            session_id: Session to update
            messages: Conversation messages
            max_tags: Maximum tags to extract

        Returns:
            List of extracted tags

        Raises:
            KeyError: If session not found
        """
        from app.services.sessions.metadata import TagExtractor

        metadata = self.get(session_id)
        if not metadata:
            raise KeyError(f"Session not found: {session_id}")

        # Extract tags
        extractor = TagExtractor()
        auto_tags = extractor.extract_tags(messages, max_tags=max_tags)

        # Update metadata
        metadata.auto_tags = auto_tags
        metadata.updated_at = datetime.utcnow()

        # Write to DB
        with self._connect() as conn:
            row = self._serialize_metadata(metadata)
            conn.execute(
                """
                UPDATE session_metadata
                SET auto_tags = :auto_tags,
                    updated_at = :updated_at
                WHERE session_id = :session_id
                """,
                row,
            )
            conn.commit()

        # Update cache
        self._cache_put(metadata)

        return auto_tags

    def update(self, session_id: str, update: MetadataUpdate) -> SessionMetadata:
        """
        Update session metadata (write-through).

        Args:
            session_id: Session to update
            update: Update specification

        Returns:
            Updated metadata

        Raises:
            KeyError: If session not found
        """
        # Get current metadata
        metadata = self.get(session_id)
        if not metadata:
            raise KeyError(f"Session not found: {session_id}")

        # Apply updates
        if update.tags is not None:
            metadata.tags = normalize_tags(update.tags)
        if update.category is not None:
            metadata.category = update.category
        if update.description is not None:
            metadata.description = normalize_description(update.description)
        if update.increment_query_count:
            metadata.query_count += 1
            metadata.last_query_at = datetime.utcnow()

        metadata.updated_at = datetime.utcnow()

        # Write to DB
        with self._connect() as conn:
            row = self._serialize_metadata(metadata)
            conn.execute(
                """
                UPDATE session_metadata
                SET tags = :tags,
                    category = :category,
                    description = :description,
                    auto_tags = :auto_tags,
                    updated_at = :updated_at,
                    query_count = :query_count,
                    last_query_at = :last_query_at
                WHERE session_id = :session_id
                """,
                row,
            )
            conn.commit()

        # Update cache
        self._cache_put(metadata)

        return metadata

    def delete(self, session_id: str) -> bool:
        """
        Delete session metadata.

        Args:
            session_id: Session to delete

        Returns:
            True if deleted, False if not found
        """
        # Delete from DB
        with self._connect() as conn:
            cursor = conn.execute("DELETE FROM session_metadata WHERE session_id = ?", (session_id,))
            conn.commit()
            deleted = cursor.rowcount > 0

        # Delete from cache
        if session_id in self._cache:
            del self._cache[session_id]

        return deleted

    def list_all(self, limit: int | None = None, offset: int = 0) -> list[SessionMetadata]:
        """
        List all session metadata from database.

        Args:
            limit: Maximum number of results (None = all)
            offset: Number of results to skip

        Returns:
            List of metadata (most recently updated first)
        """
        with self._connect() as conn:
            sql = "SELECT * FROM session_metadata ORDER BY updated_at DESC"
            params: list[Any] = []

            if limit is not None:
                sql += " LIMIT ? OFFSET ?"
                params = [limit, offset]

            cursor = conn.execute(sql, params)
            return [self._deserialize_row(row) for row in cursor.fetchall()]

    def get_all_tags(self) -> list[str]:
        """
        Get all unique tags across all sessions.

        Returns:
            Sorted list of unique tags
        """
        all_tags = set()

        with self._connect() as conn:
            cursor = conn.execute("SELECT tags, auto_tags FROM session_metadata")
            for row in cursor.fetchall():
                all_tags.update(json.loads(row["tags"]))
                all_tags.update(json.loads(row["auto_tags"]))

        return sorted(all_tags)

    def count(self) -> int:
        """
        Count total sessions in database.

        Returns:
            Total session count
        """
        with self._connect() as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM session_metadata")
            return cursor.fetchone()["count"]

    def get_stats(self) -> dict:
        """
        Get service statistics.

        Returns:
            Dictionary with stats
        """
        total_in_db = self.count()
        total_in_cache = len(self._cache)

        return {
            "total_sessions": total_in_db,
            "cached_sessions": total_in_cache,
            "max_cache_size": self.max_cache_size,
            "cache_hit_rate": total_in_cache / total_in_db if total_in_db > 0 else 0,
            "total_tags": len(self.get_all_tags()),
        }


# ============================================================================
# Singleton Instance
# ============================================================================

_metadata_db_instances: dict[Path, SessionMetadataDB] = {}


def get_metadata_db(db_path: Path | None = None) -> SessionMetadataDB:
    """
    Get singleton instance of SessionMetadataDB.

    Returns:
        Singleton database service instance
    """
    resolved_path = (db_path or SessionMetadataDB().db_path).resolve()
    if resolved_path not in _metadata_db_instances:
        _metadata_db_instances[resolved_path] = SessionMetadataDB(db_path=resolved_path)
    return _metadata_db_instances[resolved_path]
