"""
Unit tests for session metadata service.
"""

import pytest
from datetime import datetime, timedelta

from app.services.sessions.metadata import (
    SessionMetadata,
    SessionCategory,
    MetadataUpdate,
    SessionMetadataService,
    TagExtractor,
)


# ============================================================================
# TagExtractor Tests
# ============================================================================

class TestTagExtractor:
    """Test TagExtractor component."""

    def test_extract_keywords_english(self):
        """Test keyword extraction from English text."""
        extractor = TagExtractor()
        text = "machine learning algorithms for natural language processing"

        keywords = extractor.extract_keywords(text, max_keywords=5)

        assert len(keywords) > 0
        assert "machine" in keywords or "learning" in keywords
        # Stop words should be filtered
        assert "for" not in keywords

    def test_extract_keywords_chinese(self):
        """Test keyword extraction from Chinese text."""
        extractor = TagExtractor()
        text = "人工智能和机器学习技术的应用"

        keywords = extractor.extract_keywords(text, max_keywords=5)

        assert len(keywords) > 0
        # Should extract Chinese characters (tokenization treats each character as token)
        # We just verify non-empty and no stop words
        assert "的" not in keywords  # Stop word filtered

    def test_extract_domain_tags_technology(self):
        """Test technology domain tag extraction."""
        extractor = TagExtractor()
        text = "I'm working on AI and machine learning algorithms"

        tags = extractor.extract_domain_tags(text)

        assert "technology" in tags

    def test_extract_domain_tags_chinese_technology(self):
        """Test Chinese technology domain tag extraction."""
        extractor = TagExtractor()
        text = "我在研究AI和深度学习算法"

        tags = extractor.extract_domain_tags(text)

        assert "技术" in tags

    def test_extract_domain_tags_business(self):
        """Test business domain tag extraction."""
        extractor = TagExtractor()
        text = "Our product strategy and marketing plan"

        tags = extractor.extract_domain_tags(text)

        assert "business" in tags

    def test_extract_tags_from_messages(self):
        """Test tag extraction from message list."""
        extractor = TagExtractor()
        messages = [
            {"content": "How does machine learning work?"},
            {"content": "I want to learn about neural networks"},
            {"content": "Can you explain deep learning algorithms?"},
        ]

        tags = extractor.extract_tags(messages, max_tags=5)

        assert len(tags) > 0
        assert len(tags) <= 5
        # Should contain technology tag
        assert "technology" in tags or "learning" in tags

    def test_extract_tags_empty_messages(self):
        """Test tag extraction with empty messages."""
        extractor = TagExtractor()

        tags = extractor.extract_tags([], max_tags=5)

        assert tags == []

    def test_extract_tags_limits_count(self):
        """Test tag extraction respects max_tags limit."""
        extractor = TagExtractor()
        messages = [
            {"content": " ".join([f"keyword{i}" for i in range(20)])}
        ]

        tags = extractor.extract_tags(messages, max_tags=3)

        assert len(tags) <= 3


# ============================================================================
# SessionMetadataService Tests
# ============================================================================

class TestSessionMetadataService:
    """Test SessionMetadataService."""

    def test_create_metadata(self):
        """Test creating metadata."""
        service = SessionMetadataService()

        metadata = service.create_metadata(
            session_id="test1",
            tags=["AI", "技术"],
            category="research",
            description="AI research session",
        )

        assert metadata.session_id == "test1"
        assert metadata.tags == ["AI", "技术"]
        assert metadata.category == "research"
        assert metadata.description == "AI research session"
        assert metadata.query_count == 0

    def test_create_metadata_minimal(self):
        """Test creating metadata with minimal fields."""
        service = SessionMetadataService()

        metadata = service.create_metadata(session_id="test2")

        assert metadata.session_id == "test2"
        assert metadata.tags == []
        assert metadata.category is None
        assert metadata.description is None

    def test_get_metadata(self):
        """Test getting metadata."""
        service = SessionMetadataService()
        service.create_metadata(session_id="test3", tags=["tag1"])

        metadata = service.get_metadata("test3")

        assert metadata is not None
        assert metadata.session_id == "test3"
        assert metadata.tags == ["tag1"]

    def test_get_metadata_not_found(self):
        """Test getting non-existent metadata."""
        service = SessionMetadataService()

        metadata = service.get_metadata("nonexistent")

        assert metadata is None

    def test_update_metadata_tags(self):
        """Test updating tags."""
        service = SessionMetadataService()
        service.create_metadata(session_id="test4", tags=["old"])

        update = MetadataUpdate(tags=["new1", "new2"])
        metadata = service.update_metadata("test4", update)

        assert metadata.tags == ["new1", "new2"]

    def test_update_metadata_category(self):
        """Test updating category."""
        service = SessionMetadataService()
        service.create_metadata(session_id="test5")

        update = MetadataUpdate(category="work")
        metadata = service.update_metadata("test5", update)

        assert metadata.category == "work"

    def test_update_metadata_description(self):
        """Test updating description."""
        service = SessionMetadataService()
        service.create_metadata(session_id="test6")

        update = MetadataUpdate(description="New description")
        metadata = service.update_metadata("test6", update)

        assert metadata.description == "New description"

    def test_update_metadata_increment_query_count(self):
        """Test incrementing query count."""
        service = SessionMetadataService()
        service.create_metadata(session_id="test7")

        update = MetadataUpdate(increment_query_count=True)
        metadata = service.update_metadata("test7", update)

        assert metadata.query_count == 1
        assert metadata.last_query_at is not None

        # Increment again
        metadata = service.update_metadata("test7", update)
        assert metadata.query_count == 2

    def test_update_metadata_not_found(self):
        """Test updating non-existent metadata."""
        service = SessionMetadataService()

        update = MetadataUpdate(tags=["test"])

        with pytest.raises(KeyError):
            service.update_metadata("nonexistent", update)

    def test_update_metadata_updates_timestamp(self):
        """Test that update refreshes updated_at."""
        service = SessionMetadataService()
        metadata = service.create_metadata(session_id="test8")

        original_time = metadata.updated_at

        # Small delay to ensure time difference
        import time
        time.sleep(0.01)

        update = MetadataUpdate(tags=["new"])
        updated = service.update_metadata("test8", update)

        assert updated.updated_at > original_time

    def test_delete_metadata(self):
        """Test deleting metadata."""
        service = SessionMetadataService()
        service.create_metadata(session_id="test9")

        result = service.delete_metadata("test9")

        assert result is True
        assert service.get_metadata("test9") is None

    def test_delete_metadata_not_found(self):
        """Test deleting non-existent metadata."""
        service = SessionMetadataService()

        result = service.delete_metadata("nonexistent")

        assert result is False

    def test_extract_and_update_auto_tags(self):
        """Test automatic tag extraction and update."""
        service = SessionMetadataService()
        service.create_metadata(session_id="test10")

        messages = [
            {"content": "I want to learn about machine learning"},
            {"content": "How does AI work?"},
            {"content": "Explain neural networks"},
        ]

        auto_tags = service.extract_and_update_auto_tags("test10", messages)

        assert len(auto_tags) > 0
        metadata = service.get_metadata("test10")
        assert metadata.auto_tags == auto_tags

    def test_extract_auto_tags_not_found(self):
        """Test auto tag extraction for non-existent session."""
        service = SessionMetadataService()

        with pytest.raises(KeyError):
            service.extract_and_update_auto_tags("nonexistent", [])

    def test_list_all_metadata(self):
        """Test listing all metadata."""
        service = SessionMetadataService()
        service.create_metadata(session_id="list1")
        service.create_metadata(session_id="list2")
        service.create_metadata(session_id="list3")

        all_metadata = service.list_all_metadata()

        assert len(all_metadata) >= 3
        session_ids = [m.session_id for m in all_metadata]
        assert "list1" in session_ids
        assert "list2" in session_ids
        assert "list3" in session_ids

    def test_get_all_tags(self):
        """Test getting all unique tags."""
        service = SessionMetadataService()
        service.create_metadata(session_id="tags1", tags=["AI", "ML"])
        service.create_metadata(session_id="tags2", tags=["ML", "DL"])

        # Add auto tags
        metadata1 = service.get_metadata("tags1")
        metadata1.auto_tags = ["technology"]

        all_tags = service.get_all_tags()

        assert "AI" in all_tags
        assert "ML" in all_tags
        assert "DL" in all_tags
        assert "technology" in all_tags

    def test_get_all_tags_deduplicated(self):
        """Test that get_all_tags returns unique tags."""
        service = SessionMetadataService()
        service.create_metadata(session_id="dup1", tags=["AI", "ML"])
        service.create_metadata(session_id="dup2", tags=["AI", "DL"])

        all_tags = service.get_all_tags()

        # Count occurrences of "AI"
        ai_count = all_tags.count("AI")
        assert ai_count == 1  # Should appear only once


# ============================================================================
# Integration Tests
# ============================================================================

class TestSessionMetadataIntegration:
    """Test session metadata integration scenarios."""

    def test_full_lifecycle(self):
        """Test complete metadata lifecycle."""
        service = SessionMetadataService()

        # Create
        metadata = service.create_metadata(
            session_id="lifecycle",
            tags=["initial"],
            category="personal",
        )
        assert metadata.session_id == "lifecycle"

        # Update tags
        update = MetadataUpdate(tags=["updated", "tags"])
        metadata = service.update_metadata("lifecycle", update)
        assert metadata.tags == ["updated", "tags"]

        # Update category
        update = MetadataUpdate(category="work")
        metadata = service.update_metadata("lifecycle", update)
        assert metadata.category == "work"

        # Extract auto tags
        messages = [{"content": "AI and machine learning discussion"}]
        auto_tags = service.extract_and_update_auto_tags("lifecycle", messages)
        assert len(auto_tags) > 0

        # Increment query count multiple times
        for _ in range(3):
            update = MetadataUpdate(increment_query_count=True)
            service.update_metadata("lifecycle", update)

        metadata = service.get_metadata("lifecycle")
        assert metadata.query_count == 3

        # Delete
        result = service.delete_metadata("lifecycle")
        assert result is True
        assert service.get_metadata("lifecycle") is None

    def test_multiple_sessions(self):
        """Test managing multiple sessions."""
        service = SessionMetadataService()

        # Create multiple sessions
        for i in range(5):
            service.create_metadata(
                session_id=f"multi{i}",
                tags=[f"tag{i}"],
                category="research",
            )

        # List all
        all_metadata = service.list_all_metadata()
        multi_sessions = [m for m in all_metadata if m.session_id.startswith("multi")]
        assert len(multi_sessions) == 5

        # Update one
        update = MetadataUpdate(category="work")
        service.update_metadata("multi0", update)

        metadata = service.get_metadata("multi0")
        assert metadata.category == "work"

        # Others unchanged
        metadata1 = service.get_metadata("multi1")
        assert metadata1.category == "research"
