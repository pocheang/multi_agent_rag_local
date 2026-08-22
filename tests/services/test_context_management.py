"""
Unit tests for context management service.
"""

import pytest

from app.services.context_management import (
    Entity,
    EntityExtractor,
    EntityTracker,
    CoreferenceResolver,
    TopicTracker,
    ContextManagementService,
)


# ============================================================================
# EntityExtractor Tests
# ============================================================================

class TestEntityExtractor:
    """Test EntityExtractor component."""

    def test_extract_known_company(self):
        """Test extraction of known companies."""
        extractor = EntityExtractor()
        result = extractor.extract("苹果公司2023年的营收是多少？", turn=0)

        assert len(result) >= 1
        assert any(e.text in ["苹果", "苹果公司"] for e in result)
        assert any(e.type == "company" for e in result)

    def test_extract_company_with_suffix(self):
        """Test extraction of companies with suffixes."""
        extractor = EntityExtractor()
        result = extractor.extract("阿里巴巴集团的市值", turn=0)

        assert len(result) >= 1
        company_entities = [e for e in result if e.type == "company"]
        assert len(company_entities) > 0

    def test_extract_known_person(self):
        """Test extraction of known persons."""
        extractor = EntityExtractor()
        result = extractor.extract("马斯克的最新发言", turn=0)

        assert len(result) >= 1
        assert any(e.text == "马斯克" for e in result)
        assert any(e.type == "person" for e in result)

    def test_extract_person_with_title(self):
        """Test extraction of persons with titles."""
        extractor = EntityExtractor()
        result = extractor.extract("CEO库克宣布新产品", turn=0)

        person_entities = [e for e in result if e.type == "person"]
        assert len(person_entities) > 0

    def test_extract_product(self):
        """Test extraction of product names."""
        extractor = EntityExtractor()
        result = extractor.extract("iPhone 15的销量如何？", turn=0)

        assert len(result) >= 1
        assert any(e.text == "iPhone 15" for e in result)
        assert any(e.type == "product" for e in result)

    def test_extract_multiple_entities(self):
        """Test extraction of multiple entities."""
        extractor = EntityExtractor()
        result = extractor.extract("特斯拉和比亚迪的Model 3销量对比", turn=0)

        assert len(result) >= 2
        company_entities = [e for e in result if e.type == "company"]
        assert len(company_entities) >= 2

    def test_no_entities(self):
        """Test query with no entities."""
        extractor = EntityExtractor()
        result = extractor.extract("这是一个普通的查询", turn=0)

        # Should return empty or very few entities
        assert len(result) <= 1

    def test_english_company(self):
        """Test English company extraction."""
        extractor = EntityExtractor()
        result = extractor.extract("What is Apple's revenue?", turn=0)

        assert len(result) >= 1
        assert any(e.text == "Apple" for e in result)


# ============================================================================
# EntityTracker Tests
# ============================================================================

class TestEntityTracker:
    """Test EntityTracker component."""

    def test_add_single_entity(self):
        """Test adding single entity."""
        tracker = EntityTracker()
        entity = Entity(text="苹果", type="company", mention_turn=0, confidence=0.9)

        tracker.add_entities([entity])

        assert len(tracker.entities) == 1
        assert tracker.current_turn == 1

    def test_add_duplicate_entity(self):
        """Test adding duplicate entity updates existing."""
        tracker = EntityTracker()
        entity1 = Entity(text="苹果", type="company", mention_turn=0, confidence=0.9)
        entity2 = Entity(text="苹果", type="company", mention_turn=2, confidence=0.95)

        tracker.add_entities([entity1])
        tracker.add_entities([entity2])

        assert len(tracker.entities) == 1
        assert tracker.entities[0].mention_turn == 2
        assert tracker.entities[0].confidence == 0.95

    def test_get_recent_entities(self):
        """Test getting recent entities."""
        tracker = EntityTracker()
        entities = [
            Entity(text="苹果", type="company", mention_turn=0, confidence=0.9),
            Entity(text="微软", type="company", mention_turn=1, confidence=0.9),
            Entity(text="谷歌", type="company", mention_turn=2, confidence=0.9),
        ]

        for e in entities:
            tracker.add_entities([e])

        recent = tracker.get_recent_entities(n=2)

        assert len(recent) == 2
        # Most recent should be first (谷歌)
        assert recent[0].text == "谷歌"

    def test_entity_type_filter(self):
        """Test filtering entities by type."""
        tracker = EntityTracker()
        entities = [
            Entity(text="苹果", type="company", mention_turn=0, confidence=0.9),
            Entity(text="库克", type="person", mention_turn=1, confidence=0.9),
        ]

        for e in entities:
            tracker.add_entities([e])

        companies = tracker.get_recent_entities(entity_type="company")
        persons = tracker.get_recent_entities(entity_type="person")

        assert len(companies) == 1
        assert companies[0].text == "苹果"
        assert len(persons) == 1
        assert persons[0].text == "库克"

    def test_decay_weighting(self):
        """Test decay weighting of old entities."""
        tracker = EntityTracker()

        # Add entity at turn 0
        old_entity = Entity(text="微软", type="company", mention_turn=0, confidence=1.0)
        tracker.add_entities([old_entity])

        # Add several more turns
        for i in range(1, 6):
            tracker.add_entities([
                Entity(text=f"dummy{i}", type="other", mention_turn=i, confidence=0.5)
            ])

        # Old entity should have lower weight due to decay
        recent = tracker.get_recent_entities(n=10)
        old_entity_in_recent = next(e for e in recent if e.text == "微软")

        # Check it's not at the top (due to decay)
        assert recent.index(old_entity_in_recent) > 0

    def test_find_most_relevant(self):
        """Test finding most relevant entity."""
        tracker = EntityTracker()
        entities = [
            Entity(text="苹果", type="company", mention_turn=0, confidence=0.9),
            Entity(text="微软", type="company", mention_turn=1, confidence=0.9),
        ]

        for e in entities:
            tracker.add_entities([e])

        most_relevant = tracker.find_most_relevant()

        assert most_relevant is not None
        assert most_relevant.text == "微软"  # Most recent


# ============================================================================
# CoreferenceResolver Tests
# ============================================================================

class TestCoreferenceResolver:
    """Test CoreferenceResolver component."""

    def test_no_coreference(self):
        """Test query without coreference."""
        resolver = CoreferenceResolver()
        tracker = EntityTracker()

        result = resolver.resolve("苹果公司的营收是多少？", tracker)

        assert result.original == result.resolved
        assert len(result.entities_resolved) == 0
        assert result.confidence == 1.0

    def test_simple_coreference_chinese(self):
        """Test simple Chinese coreference resolution."""
        resolver = CoreferenceResolver()
        tracker = EntityTracker()

        # Add entity to context
        tracker.add_entities([
            Entity(text="苹果", type="company", mention_turn=0, confidence=0.9)
        ])

        result = resolver.resolve("它的市场份额是多少？", tracker)

        assert result.resolved == "苹果的市场份额是多少？"
        assert "苹果" in result.entities_resolved
        assert result.confidence > 0.6

    def test_simple_coreference_english(self):
        """Test simple English coreference resolution."""
        resolver = CoreferenceResolver()
        tracker = EntityTracker()

        # Add entity to context
        tracker.add_entities([
            Entity(text="Apple", type="company", mention_turn=0, confidence=0.9)
        ])

        result = resolver.resolve("What is its market share?", tracker)

        assert "Apple" in result.resolved
        assert "Apple" in result.entities_resolved
        assert result.confidence > 0.6

    def test_no_entities_in_context(self):
        """Test coreference when no entities in context."""
        resolver = CoreferenceResolver()
        tracker = EntityTracker()

        result = resolver.resolve("它的市场份额是多少？", tracker)

        assert result.needs_clarification
        assert len(result.entities_resolved) == 0

    def test_entity_type_matching(self):
        """Test entity type matching with pronouns."""
        resolver = CoreferenceResolver()
        tracker = EntityTracker()

        # Add person and company
        tracker.add_entities([
            Entity(text="库克", type="person", mention_turn=0, confidence=0.9),
            Entity(text="苹果", type="company", mention_turn=1, confidence=0.9),
        ])

        # "它" should match company, not person
        result = resolver.resolve("它的产品线", tracker)

        assert "苹果" in result.resolved
        assert "库克" not in result.resolved

    def test_multiple_candidates(self):
        """Test resolution with multiple candidates."""
        resolver = CoreferenceResolver()
        tracker = EntityTracker()

        # Add multiple companies
        tracker.add_entities([
            Entity(text="特斯拉", type="company", mention_turn=0, confidence=0.9),
            Entity(text="比亚迪", type="company", mention_turn=1, confidence=0.9),
        ])

        result = resolver.resolve("它的销量", tracker)

        # Should resolve to most recent (比亚迪)
        assert "比亚迪" in result.resolved


# ============================================================================
# TopicTracker Tests
# ============================================================================

class TestTopicTracker:
    """Test TopicTracker component."""

    def test_extract_financial_topic(self):
        """Test extracting financial topic."""
        tracker = TopicTracker()

        topic = tracker.extract_topic("公司的营收和利润情况", [])

        assert topic == "财务分析"

    def test_extract_market_topic(self):
        """Test extracting market competition topic."""
        tracker = TopicTracker()

        topic = tracker.extract_topic("市场份额和竞争对手分析", [])

        assert topic == "市场竞争"

    def test_extract_product_topic(self):
        """Test extracting product topic."""
        tracker = TopicTracker()

        topic = tracker.extract_topic("新产品的技术创新", [])

        assert topic == "产品技术"

    def test_no_clear_topic(self):
        """Test query with no clear topic."""
        tracker = TopicTracker()

        topic = tracker.extract_topic("一般性问题", [])

        assert topic is None

    def test_topic_switch_detection(self):
        """Test topic switch detection."""
        tracker = TopicTracker()

        is_switch = tracker.is_topic_switch("财务分析", "市场竞争")

        assert is_switch

    def test_no_topic_switch(self):
        """Test no topic switch."""
        tracker = TopicTracker()

        is_switch = tracker.is_topic_switch("财务分析", "财务分析")

        assert not is_switch


# ============================================================================
# ContextManagementService Tests
# ============================================================================

class TestContextManagementService:
    """Test ContextManagementService integration."""

    def test_process_first_query(self):
        """Test processing first query in session."""
        service = ContextManagementService()

        result = service.process_query("苹果公司的营收", session_id="test")

        assert result.original == "苹果公司的营收"
        assert result.confidence > 0

    def test_process_with_coreference(self):
        """Test processing query with coreference."""
        service = ContextManagementService()

        # First query
        service.process_query("苹果公司2023年的营收", session_id="test")

        # Second query with coreference
        result = service.process_query("它的市场份额", session_id="test")

        assert "苹果" in result.resolved or "苹果公司" in result.resolved

    def test_session_isolation(self):
        """Test that sessions are isolated."""
        service = ContextManagementService()

        # Session 1
        service.process_query("苹果公司的营收", session_id="session1")

        # Session 2 should not have access to session1's entities
        result = service.process_query("它的市场份额", session_id="session2")

        assert result.needs_clarification or result.resolved == result.original

    def test_clear_context(self):
        """Test clearing context."""
        service = ContextManagementService()

        # Add some context
        service.process_query("苹果公司的营收", session_id="test")

        # Clear
        service.clear_context("test")

        # Should not have context
        context = service.get_context("test")
        assert context is None

    def test_get_context(self):
        """Test getting current context."""
        service = ContextManagementService()

        # Process query
        service.process_query("苹果公司的营收", session_id="test")

        # Get context
        context = service.get_context("test")

        assert context is not None
        assert context.session_id == "test"
        assert context.turn_count == 1

    def test_multiple_turns(self):
        """Test multiple conversation turns."""
        service = ContextManagementService()

        # Turn 1
        service.process_query("特斯拉和比亚迪的销量", session_id="test")

        # Turn 2
        service.process_query("它们的市场份额", session_id="test")

        # Turn 3
        result = service.process_query("第一家公司的技术", session_id="test")

        # Should have entities from all turns
        context = service.get_context("test")
        assert context is not None
        assert context.turn_count == 3


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_query(self):
        """Test empty query handling."""
        service = ContextManagementService()

        result = service.process_query("", session_id="test")

        assert result.original == ""
        assert result.resolved == ""

    def test_very_long_query(self):
        """Test very long query."""
        service = ContextManagementService()

        long_query = "苹果公司" + "的营收情况" * 100
        result = service.process_query(long_query, session_id="test")

        assert result.confidence > 0

    def test_mixed_language(self):
        """Test mixed Chinese-English query."""
        service = ContextManagementService()

        result = service.process_query("Apple公司的revenue是多少", session_id="test")

        assert result.confidence > 0

    def test_special_characters(self):
        """Test query with special characters."""
        service = ContextManagementService()

        result = service.process_query("公司的营收(2023年)是多少？", session_id="test")

        assert result.confidence > 0
