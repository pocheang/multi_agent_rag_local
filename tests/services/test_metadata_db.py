"""
Integration tests for database-backed session metadata service.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

from app.services.sessions.metadata import SessionMetadata, MetadataUpdate
from app.services.sessions.metadata_db import SessionMetadataDB


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = Path(f.name)

    yield db_path

    # Cleanup (try to delete, ignore if locked on Windows)
    try:
        if db_path.exists():
            db_path.unlink()
        # Also clean up WAL files
        for ext in ["-wal", "-shm"]:
            wal_file = Path(str(db_path) + ext)
            if wal_file.exists():
                wal_file.unlink(missing_ok=True)
    except PermissionError:
        # Windows file lock - ignore
        pass


@pytest.fixture
def db_service(temp_db):
    """Create fresh database service for each test."""
    return SessionMetadataDB(db_path=temp_db, max_cache_size=5)


# ============================================================================
# Basic CRUD Tests
# ============================================================================

def test_create_and_get(db_service):
    """Test creating and retrieving metadata."""
    metadata = SessionMetadata(
        session_id="test-1",
        tags=["python", "testing"],
        category="development",
        description="Test session"
    )

    # Create
    created = db_service.create(metadata)
    assert created.session_id == "test-1"
    assert created.tags == ["python", "testing"]

    # Get (should hit cache)
    retrieved = db_service.get("test-1")
    assert retrieved is not None
    assert retrieved.session_id == "test-1"
    assert retrieved.tags == ["python", "testing"]


def test_create_duplicate_fails(db_service):
    """Test that creating duplicate session fails."""
    metadata = SessionMetadata(session_id="test-1", tags=["tag1"])

    db_service.create(metadata)

    # Attempt duplicate
    with pytest.raises(ValueError, match="already exists"):
        db_service.create(metadata)


def test_get_nonexistent_returns_none(db_service):
    """Test getting non-existent session returns None."""
    result = db_service.get("nonexistent")
    assert result is None


def test_update_metadata(db_service):
    """Test updating metadata."""
    metadata = SessionMetadata(
        session_id="test-1",
        tags=["old"],
        category="work"
    )
    db_service.create(metadata)

    # Update
    update = MetadataUpdate(
        tags=["new", "updated"],
        category="personal",
        description="Updated description"
    )
    updated = db_service.update("test-1", update)

    assert updated.tags == ["new", "updated"]
    assert updated.category == "personal"
    assert updated.description == "Updated description"

    # Verify in DB
    retrieved = db_service.get("test-1")
    assert retrieved.tags == ["new", "updated"]


def test_update_nonexistent_fails(db_service):
    """Test updating non-existent session fails."""
    update = MetadataUpdate(tags=["new"])

    with pytest.raises(KeyError):
        db_service.update("nonexistent", update)


def test_delete_metadata(db_service):
    """Test deleting metadata."""
    metadata = SessionMetadata(session_id="test-1", tags=["tag1"])
    db_service.create(metadata)

    # Delete
    deleted = db_service.delete("test-1")
    assert deleted is True

    # Verify gone
    assert db_service.get("test-1") is None

    # Delete again
    deleted_again = db_service.delete("test-1")
    assert deleted_again is False


# ============================================================================
# Persistence Tests
# ============================================================================

def test_persistence_across_instances(temp_db):
    """Test data persists across service instances."""
    # Create data with first instance
    service1 = SessionMetadataDB(db_path=temp_db, max_cache_size=5)
    metadata = SessionMetadata(
        session_id="test-1",
        tags=["persistent"],
        description="Survives restart"
    )
    service1.create(metadata)

    # Create new instance (simulating restart)
    service2 = SessionMetadataDB(db_path=temp_db, max_cache_size=5)

    # Data should be in DB
    retrieved = service2.get("test-1")
    assert retrieved is not None
    assert retrieved.session_id == "test-1"
    assert retrieved.tags == ["persistent"]
    assert retrieved.description == "Survives restart"


def test_cache_warming_on_get(temp_db):
    """Test that get() warms the cache from DB."""
    # Create data with first instance
    service1 = SessionMetadataDB(db_path=temp_db, max_cache_size=5)
    metadata = SessionMetadata(session_id="test-1", tags=["tag1"])
    service1.create(metadata)

    # New instance with empty cache
    service2 = SessionMetadataDB(db_path=temp_db, max_cache_size=5)
    assert len(service2._cache) == 0

    # Get should load from DB and warm cache
    retrieved = service2.get("test-1")
    assert retrieved is not None
    assert len(service2._cache) == 1
    assert "test-1" in service2._cache


# ============================================================================
# Cache Tests
# ============================================================================

def test_lru_cache_eviction(db_service):
    """Test LRU cache evicts oldest entries."""
    # Fill cache to capacity (5)
    for i in range(5):
        metadata = SessionMetadata(session_id=f"test-{i}", tags=[f"tag{i}"])
        db_service.create(metadata)

    assert len(db_service._cache) == 5

    # Add 6th session - should evict test-0
    metadata6 = SessionMetadata(session_id="test-6", tags=["tag6"])
    db_service.create(metadata6)

    assert len(db_service._cache) == 5
    assert "test-0" not in db_service._cache
    assert "test-6" in db_service._cache

    # But test-0 should still be in DB
    retrieved = db_service.get("test-0")
    assert retrieved is not None
    assert retrieved.tags == ["tag0"]


def test_cache_touch_on_get(db_service):
    """Test that get() touches cache entry (LRU)."""
    # Create 5 sessions
    for i in range(5):
        metadata = SessionMetadata(session_id=f"test-{i}", tags=[f"tag{i}"])
        db_service.create(metadata)

    # Access test-0 (moves to end)
    db_service.get("test-0")

    # Add 6th session - should evict test-1 (now oldest)
    metadata6 = SessionMetadata(session_id="test-6", tags=["tag6"])
    db_service.create(metadata6)

    assert "test-0" in db_service._cache  # Still in cache (touched)
    assert "test-1" not in db_service._cache  # Evicted


def test_cache_update_on_write(db_service):
    """Test that update() refreshes cache."""
    metadata = SessionMetadata(session_id="test-1", tags=["old"])
    db_service.create(metadata)

    # Update
    update = MetadataUpdate(tags=["new"])
    db_service.update("test-1", update)

    # Cache should have updated value
    cached = db_service._cache.get("test-1")
    assert cached is not None
    assert cached.tags == ["new"]


# ============================================================================
# Query Tests
# ============================================================================

def test_list_all(db_service):
    """Test listing all metadata."""
    # Create multiple sessions
    for i in range(3):
        metadata = SessionMetadata(
            session_id=f"test-{i}",
            tags=[f"tag{i}"]
        )
        db_service.create(metadata)

    # List all
    all_metadata = db_service.list_all()
    assert len(all_metadata) == 3

    # Should be ordered by updated_at DESC
    assert all_metadata[0].session_id == "test-2"  # Most recent


def test_list_all_with_pagination(db_service):
    """Test pagination in list_all."""
    # Create 10 sessions
    for i in range(10):
        metadata = SessionMetadata(session_id=f"test-{i}", tags=[f"tag{i}"])
        db_service.create(metadata)

    # Get first page
    page1 = db_service.list_all(limit=3, offset=0)
    assert len(page1) == 3

    # Get second page
    page2 = db_service.list_all(limit=3, offset=3)
    assert len(page2) == 3

    # Pages should be different
    assert page1[0].session_id != page2[0].session_id


def test_get_all_tags(db_service):
    """Test getting all unique tags."""
    metadata1 = SessionMetadata(
        session_id="test-1",
        tags=["python", "fastapi"],
        auto_tags=["api"]
    )
    metadata2 = SessionMetadata(
        session_id="test-2",
        tags=["python", "django"],
        auto_tags=["web"]
    )

    db_service.create(metadata1)
    db_service.create(metadata2)

    all_tags = db_service.get_all_tags()
    assert set(all_tags) == {"api", "django", "fastapi", "python", "web"}


def test_count(db_service):
    """Test counting total sessions."""
    assert db_service.count() == 0

    for i in range(5):
        metadata = SessionMetadata(session_id=f"test-{i}", tags=[f"tag{i}"])
        db_service.create(metadata)

    assert db_service.count() == 5


def test_get_stats(db_service):
    """Test service statistics."""
    # Create 3 sessions
    for i in range(3):
        metadata = SessionMetadata(session_id=f"test-{i}", tags=[f"tag{i}"])
        db_service.create(metadata)

    stats = db_service.get_stats()
    assert stats["total_sessions"] == 3
    assert stats["cached_sessions"] == 3
    assert stats["max_cache_size"] == 5
    assert stats["total_tags"] == 3


# ============================================================================
# Edge Cases
# ============================================================================

def test_empty_database(db_service):
    """Test operations on empty database."""
    assert db_service.count() == 0
    assert db_service.list_all() == []
    assert db_service.get_all_tags() == []
    assert db_service.get("nonexistent") is None


def test_auto_tags_persistence(db_service):
    """Test that auto_tags are persisted correctly."""
    metadata = SessionMetadata(
        session_id="test-1",
        tags=["manual"],
        auto_tags=["auto1", "auto2"]
    )
    db_service.create(metadata)

    # Retrieve
    retrieved = db_service.get("test-1")
    assert retrieved.auto_tags == ["auto1", "auto2"]


def test_datetime_serialization(db_service):
    """Test that datetimes are serialized/deserialized correctly."""
    now = datetime.utcnow()
    metadata = SessionMetadata(
        session_id="test-1",
        tags=["tag1"],
        created_at=now,
        updated_at=now,
        last_query_at=now
    )
    db_service.create(metadata)

    # Retrieve
    retrieved = db_service.get("test-1")

    # Datetime precision might differ slightly, check within 1 second
    assert abs((retrieved.created_at - now).total_seconds()) < 1
    assert abs((retrieved.updated_at - now).total_seconds()) < 1
    assert retrieved.last_query_at is not None
    assert abs((retrieved.last_query_at - now).total_seconds()) < 1


def test_null_fields(db_service):
    """Test handling of null optional fields."""
    metadata = SessionMetadata(
        session_id="test-1",
        tags=[],
        category=None,
        description=None
    )
    db_service.create(metadata)

    retrieved = db_service.get("test-1")
    assert retrieved.category is None
    assert retrieved.description is None
    assert retrieved.last_query_at is None
