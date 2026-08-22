"""
Unit tests for SessionMetadataService with validation and capacity limits.
"""

import pytest
from datetime import datetime

from app.services.sessions.metadata import (
    SessionMetadata,
    MetadataUpdate,
    SessionMetadataService,
    MAX_TAG_LENGTH,
    MAX_DESCRIPTION_LENGTH,
    MAX_TAGS_PER_SESSION,
)


@pytest.fixture
def service():
    """Create a fresh service instance for each test."""
    return SessionMetadataService(max_sessions=5)  # Small capacity for testing


# ============================================================================
# Input Validation Tests
# ============================================================================

def test_create_with_valid_tags(service):
    """Test creating metadata with valid tags."""
    metadata = service.create_metadata(
        "test-1",
        tags=["python", "fastapi", "test_tag", "tag-123"],
    )
    assert metadata.session_id == "test-1"
    assert set(metadata.tags) == {"python", "fastapi", "test_tag", "tag-123"}


def test_create_with_invalid_tag_special_chars(service):
    """Test that tags with special characters are rejected."""
    with pytest.raises(ValueError, match="Invalid tag"):
        service.create_metadata(
            "test-1",
            tags=["valid-tag", "invalid tag"],  # Space not allowed
        )


def test_create_with_invalid_tag_too_long(service):
    """Test that overly long tags are rejected."""
    long_tag = "a" * (MAX_TAG_LENGTH + 1)
    with pytest.raises(ValueError, match="exceeds maximum length"):
        service.create_metadata("test-1", tags=[long_tag])


def test_create_with_too_many_tags(service):
    """Test that tag count limit is enforced."""
    too_many_tags = [f"tag{i}" for i in range(MAX_TAGS_PER_SESSION + 1)]
    with pytest.raises(ValueError, match="Too many tags"):
        service.create_metadata("test-1", tags=too_many_tags)


def test_create_with_duplicate_tags(service):
    """Test that duplicate tags are deduplicated."""
    metadata = service.create_metadata(
        "test-1",
        tags=["python", "Python", "PYTHON", "python"],  # All same
    )
    assert metadata.tags == ["python"]  # Only one, normalized


def test_create_with_description_too_long(service):
    """Test that overly long descriptions are rejected."""
    long_desc = "x" * (MAX_DESCRIPTION_LENGTH + 1)
    with pytest.raises(ValueError, match="exceeds maximum length"):
        service.create_metadata("test-1", description=long_desc)


def test_create_with_valid_description(service):
    """Test creating metadata with valid description."""
    metadata = service.create_metadata(
        "test-1",
        description="  Valid description  ",  # Trimmed
    )
    assert metadata.description == "Valid description"


def test_create_with_empty_description(service):
    """Test that empty/whitespace description becomes None."""
    metadata = service.create_metadata("test-1", description="   ")
    assert metadata.description is None


def test_update_with_invalid_tags(service):
    """Test that update validation works."""
    service.create_metadata("test-1", tags=["valid"])

    with pytest.raises(ValueError, match="Invalid tag"):
        service.update_metadata(
            "test-1",
            MetadataUpdate(tags=["invalid tag"]),  # Space not allowed
        )


def test_update_with_invalid_description(service):
    """Test that update description validation works."""
    service.create_metadata("test-1")

    long_desc = "x" * (MAX_DESCRIPTION_LENGTH + 1)
    with pytest.raises(ValueError, match="exceeds maximum length"):
        service.update_metadata(
            "test-1",
            MetadataUpdate(description=long_desc),
        )


# ============================================================================
# LRU Capacity Tests
# ============================================================================

def test_lru_eviction_on_capacity(service):
    """Test that oldest sessions are evicted when at capacity."""
    # Service has max_sessions=5
    for i in range(6):
        service.create_metadata(f"session-{i}", tags=[f"tag{i}"])

    # session-0 should be evicted
    assert service.get_metadata("session-0") is None
    assert service.get_metadata("session-5") is not None

    # Verify only 5 sessions exist
    all_sessions = service.list_all()
    assert len(all_sessions) == 5


def test_lru_touch_on_get(service):
    """Test that get_metadata touches LRU."""
    # Create 5 sessions
    for i in range(5):
        service.create_metadata(f"session-{i}")

    # Access session-0 (moves to end)
    service.get_metadata("session-0")

    # Create new session (should evict session-1, not session-0)
    service.create_metadata("session-5")

    assert service.get_metadata("session-0") is not None  # Still exists
    assert service.get_metadata("session-1") is None  # Evicted


def test_lru_touch_on_update(service):
    """Test that update_metadata touches LRU."""
    # Create 5 sessions
    for i in range(5):
        service.create_metadata(f"session-{i}")

    # Update session-0 (moves to end)
    service.update_metadata("session-0", MetadataUpdate(tags=["updated"]))

    # Create new session (should evict session-1, not session-0)
    service.create_metadata("session-5")

    assert service.get_metadata("session-0") is not None
    assert service.get_metadata("session-1") is None


# ============================================================================
# Tag Normalization Tests
# ============================================================================

def test_tag_case_normalization(service):
    """Test that tags are normalized to lowercase."""
    metadata = service.create_metadata(
        "test-1",
        tags=["Python", "FastAPI", "TEST"],
    )
    assert metadata.tags == ["python", "fastapi", "test"]


def test_tag_whitespace_trimming(service):
    """Test that tag whitespace is trimmed."""
    metadata = service.create_metadata(
        "test-1",
        tags=["  python  ", "fastapi"],
    )
    assert metadata.tags == ["python", "fastapi"]


# ============================================================================
# Stats Tests
# ============================================================================

def test_get_stats(service):
    """Test service statistics."""
    service.create_metadata("test-1", tags=["tag1", "tag2"])
    service.create_metadata("test-2", tags=["tag2", "tag3"])

    stats = service.get_stats()
    assert stats["total_sessions"] == 2
    assert stats["max_capacity"] == 5
    assert stats["total_tags"] == 3  # tag1, tag2, tag3


def test_get_all_tags(service):
    """Test getting all unique tags."""
    service.create_metadata("test-1", tags=["python", "fastapi"])
    service.create_metadata("test-2", tags=["python", "django"])

    # Also add auto_tags
    metadata = service.get_metadata("test-1")
    metadata.auto_tags = ["ml", "ai"]

    all_tags = service.get_all_tags()
    assert set(all_tags) == {"python", "fastapi", "django", "ml", "ai"}


# ============================================================================
# Edge Cases
# ============================================================================

def test_create_duplicate_session_id(service):
    """Test that duplicate session IDs are rejected."""
    service.create_metadata("test-1")

    with pytest.raises(ValueError, match="already exists"):
        service.create_metadata("test-1")


def test_update_nonexistent_session(service):
    """Test that updating nonexistent session raises KeyError."""
    with pytest.raises(KeyError):
        service.update_metadata("nonexistent", MetadataUpdate(tags=["tag"]))


def test_delete_success(service):
    """Test successful deletion."""
    service.create_metadata("test-1")
    assert service.delete_metadata("test-1") is True
    assert service.get_metadata("test-1") is None


def test_delete_nonexistent(service):
    """Test deleting nonexistent session returns False."""
    assert service.delete_metadata("nonexistent") is False


def test_empty_tags_list(service):
    """Test creating metadata with empty tags list."""
    metadata = service.create_metadata("test-1", tags=[])
    assert metadata.tags == []


def test_none_values(service):
    """Test creating metadata with None values."""
    metadata = service.create_metadata(
        "test-1",
        tags=None,
        category=None,
        description=None,
    )
    assert metadata.tags == []
    assert metadata.category is None
    assert metadata.description is None
