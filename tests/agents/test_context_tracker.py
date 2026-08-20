"""
Tests for Context Tracker Agent.
"""

import asyncio
import time
from datetime import datetime, timedelta

import pytest

from app.services.sessions.context_tracker import (
    cleanup_expired_contexts,
    clear_context,
    get_context,
    get_context_aware_routing_hints,
    get_all_sessions,
    get_store_stats,
    resolve_query_with_context,
    update_conversation_context,
    _context_store,
    _detect_intent,
    _is_followup_query,
    _detect_reference_pronouns,
    _get_top_entities,
)
from app.agents.quality_models import ConversationContext, ConversationTurn, ContextHints


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture(autouse=True)
def clean_store():
    """Clean context store before and after each test."""
    _context_store.clear()
    yield
    _context_store.clear()


@pytest.fixture
def sample_session_id():
    """Sample session ID."""
    return "test-session-123"


@pytest.fixture
def sample_user_id():
    """Sample user ID."""
    return "user-456"


@pytest.fixture
async def populated_context(sample_session_id, sample_user_id):
    """Create a populated conversation context."""
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="What is Python?",
        response="Python is a programming language.",
        route="vector",
        entities=["Python", "programming language"],
    )
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="Tell me more about it",
        response="Python is high-level and interpreted.",
        route="vector",
        entities=["Python"],
    )
    return get_context(sample_session_id, sample_user_id)


# ============================================================================
# Test Context Creation and Updates
# ============================================================================


@pytest.mark.asyncio
async def test_create_new_context(sample_session_id, sample_user_id):
    """Test creating a new conversation context."""
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="Hello world",
        response="Hi there!",
        route="vector",
        entities=["world"],
    )

    context = get_context(sample_session_id, sample_user_id)
    assert context is not None
    assert get_context(sample_session_id, "other-user") is None
    assert context.session_id == sample_session_id
    assert context.user_id == sample_user_id
    assert len(context.conversation_history) == 1
    assert context.conversation_history[0].query == "Hello world"
    assert context.conversation_history[0].response == "Hi there!"
    assert context.conversation_history[0].route == "vector"
    assert "world" in context.conversation_history[0].entities


@pytest.mark.asyncio
async def test_update_existing_context(sample_session_id, sample_user_id):
    """Test updating an existing context."""
    # First turn
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="First query",
        response="First response",
        route="vector",
        entities=["entity1"],
    )

    # Second turn
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="Second query",
        response="Second response",
        route="hybrid",
        entities=["entity2"],
    )

    context = get_context(sample_session_id, sample_user_id)
    assert len(context.conversation_history) == 2
    assert context.conversation_history[0].query == "First query"
    assert context.conversation_history[1].query == "Second query"
    assert len(context.topic_stack) == 2
    assert context.topic_stack == ["vector", "hybrid"]


@pytest.mark.asyncio
async def test_context_update_performance(sample_session_id, sample_user_id):
    """Test that context updates meet <10ms performance requirement."""
    # Pre-populate with some history
    for i in range(5):
        await update_conversation_context(
            session_id=sample_session_id,
            user_id=sample_user_id,
            query=f"Query {i}",
            response=f"Response {i}",
            route="vector",
            entities=[f"entity{i}"],
        )

    # Measure incremental update
    start = time.perf_counter()
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="Performance test query",
        response="Performance test response",
        route="hybrid",
        entities=["test_entity"],
    )
    elapsed_ms = (time.perf_counter() - start) * 1000

    # Should be well under 10ms for incremental update
    assert elapsed_ms < 10.0, f"Update took {elapsed_ms:.2f}ms, expected <10ms"


@pytest.mark.asyncio
async def test_history_limit_enforcement(sample_session_id, sample_user_id):
    """Test that conversation history respects max turns limit."""
    # Add 15 turns (max is 10)
    for i in range(15):
        await update_conversation_context(
            session_id=sample_session_id,
            user_id=sample_user_id,
            query=f"Query {i}",
            response=f"Response {i}",
            route="vector",
            entities=[],
        )

    context = get_context(sample_session_id, sample_user_id)
    assert len(context.conversation_history) == 10
    # Should keep the most recent 10
    assert context.conversation_history[0].query == "Query 5"
    assert context.conversation_history[-1].query == "Query 14"


@pytest.mark.asyncio
async def test_entity_mention_tracking(sample_session_id, sample_user_id):
    """Test entity mention frequency tracking."""
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="Tell me about Python",
        response="Python is great",
        route="vector",
        entities=["Python"],
    )
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="More about Python and Java",
        response="Both are languages",
        route="vector",
        entities=["Python", "Java"],
    )
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="Python features",
        response="Python has many features",
        route="vector",
        entities=["Python"],
    )

    context = get_context(sample_session_id, sample_user_id)
    assert context.entity_mentions["Python"] == 3
    assert context.entity_mentions["Java"] == 1


# ============================================================================
# Test Context Hints Generation
# ============================================================================


def test_hints_for_new_session():
    """Test hints for a new session with no context."""
    hints = get_context_aware_routing_hints("nonexistent-session", "What is AI?")

    assert hints.followup is False
    assert hints.previous_route is None
    assert hints.resolve_references is None
    assert len(hints.focus_entities) == 0


@pytest.mark.asyncio
async def test_hints_for_followup_query(sample_session_id, sample_user_id):
    """Test follow-up detection."""
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="What is machine learning?",
        response="Machine learning is...",
        route="vector",
        entities=["machine learning"],
    )

    # Follow-up indicators
    hints1 = get_context_aware_routing_hints(sample_session_id, "Tell me more", sample_user_id)
    assert hints1.followup is True

    hints2 = get_context_aware_routing_hints(
        sample_session_id, "Also, what about deep learning?", sample_user_id
    )
    assert hints2.followup is True

    hints3 = get_context_aware_routing_hints(sample_session_id, "还有什么?", sample_user_id)
    assert hints3.followup is True


@pytest.mark.asyncio
async def test_hints_previous_route(sample_session_id, sample_user_id):
    """Test previous route tracking in hints."""
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="Query",
        response="Response",
        route="hybrid",
        entities=[],
    )

    hints = get_context_aware_routing_hints(sample_session_id, "Follow-up", sample_user_id)
    assert hints.previous_route == "hybrid"


@pytest.mark.asyncio
async def test_hints_focus_entities(sample_session_id, sample_user_id):
    """Test focus entities in hints."""
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="Query 1",
        response="Response 1",
        route="vector",
        entities=["Python", "Java", "C++"],
    )
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="Query 2",
        response="Response 2",
        route="vector",
        entities=["Python", "Java"],
    )
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="Query 3",
        response="Response 3",
        route="vector",
        entities=["Python"],
    )

    hints = get_context_aware_routing_hints(sample_session_id, "Next query", sample_user_id)
    # Should return top 3 entities by mention count
    assert "Python" in hints.focus_entities  # 3 mentions
    assert "Java" in hints.focus_entities     # 2 mentions
    assert "C++" in hints.focus_entities      # 1 mention


@pytest.mark.asyncio
async def test_hints_generation_performance(sample_session_id, sample_user_id):
    """Test that hint generation meets <5ms performance requirement."""
    # Populate with history
    for i in range(10):
        await update_conversation_context(
            session_id=sample_session_id,
            user_id=sample_user_id,
            query=f"Query {i}",
            response=f"Response {i}",
            route="vector",
            entities=[f"entity{i % 3}"],  # Repeat some entities
        )

    # Measure hint generation
    start = time.perf_counter()
    hints = get_context_aware_routing_hints(sample_session_id, "Test query", sample_user_id)
    elapsed_ms = (time.perf_counter() - start) * 1000

    assert elapsed_ms < 5.0, f"Hint generation took {elapsed_ms:.2f}ms, expected <5ms"
    assert hints is not None


# ============================================================================
# Test Query Resolution
# ============================================================================


def test_resolve_query_no_hints():
    """Test query resolution with no hints."""
    query = "What is machine learning?"
    hints = ContextHints(
        resolve_references=None,
        followup=False,
        previous_route=None,
        focus_entities=[],
    )

    resolved = resolve_query_with_context(query, hints)
    assert resolved == query  # No change


def test_resolve_query_chinese_pronouns():
    """Test Chinese pronoun resolution."""
    query = "它是什么?"
    hints = ContextHints(
        resolve_references={"Python": 3},
        followup=True,
        previous_route="vector",
        focus_entities=["Python"],
    )

    resolved = resolve_query_with_context(query, hints)
    assert "Python" in resolved
    assert "它" not in resolved


def test_resolve_query_english_pronouns():
    """Test English pronoun resolution."""
    query = "Tell me more about it"
    hints = ContextHints(
        resolve_references={"TensorFlow": 2},
        followup=True,
        previous_route="vector",
        focus_entities=["TensorFlow"],
    )

    resolved = resolve_query_with_context(query, hints)
    assert "TensorFlow" in resolved
    # "it" should be replaced with "TensorFlow"


def test_resolve_query_multiple_references():
    """Test resolution with multiple reference entities."""
    query = "Compare this with that"
    hints = ContextHints(
        resolve_references={"Python": 5, "Java": 3, "C++": 1},
        followup=True,
        previous_route="vector",
        focus_entities=["Python", "Java", "C++"],
    )

    resolved = resolve_query_with_context(query, hints)
    # Should resolve to the most mentioned entities
    assert "Python" in resolved or "Java" in resolved


# ============================================================================
# Test Context Cleanup
# ============================================================================


@pytest.mark.asyncio
async def test_cleanup_expired_contexts(sample_user_id):
    """Test TTL-based context cleanup."""
    # Create contexts with different timestamps
    session1 = "session-1"
    session2 = "session-2"

    # Recent context
    await update_conversation_context(
        session_id=session1,
        user_id=sample_user_id,
        query="Recent query",
        response="Recent response",
        route="vector",
        entities=[],
    )

    # Old context (manually set timestamp)
    await update_conversation_context(
        session_id=session2,
        user_id=sample_user_id,
        query="Old query",
        response="Old response",
        route="vector",
        entities=[],
    )
    # Manually age the context
    old_context = get_context(session2, sample_user_id)
    assert old_context is not None
    old_context.last_update_time = datetime.utcnow() - timedelta(hours=2)

    # Cleanup expired (TTL is 3600 seconds = 1 hour)
    cleaned = cleanup_expired_contexts()

    assert cleaned == 1
    assert get_context(session1, sample_user_id) is not None
    assert get_context(session2, sample_user_id) is None


@pytest.mark.asyncio
async def test_clear_context(sample_session_id, sample_user_id):
    """Test manual context clearing."""
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="Test",
        response="Test",
        route="vector",
        entities=[],
    )

    assert get_context(sample_session_id, sample_user_id) is not None

    cleared = clear_context(sample_session_id, sample_user_id)
    assert cleared is True
    assert get_context(sample_session_id, sample_user_id) is None

    # Clearing non-existent context should return False
    cleared_again = clear_context(sample_session_id, sample_user_id)
    assert cleared_again is False


# ============================================================================
# Test Helper Functions
# ============================================================================


def test_detect_intent_question():
    """Test intent detection for questions."""
    assert _detect_intent("What is AI?") == "question"
    assert _detect_intent("How does it work?") == "question"
    assert _detect_intent("为什么选择Python?") == "question"


def test_detect_intent_navigation():
    """Test intent detection for navigation."""
    assert _detect_intent("Show me examples") == "navigation"
    assert _detect_intent("Find all documents") == "navigation"
    assert _detect_intent("搜索相关资料") == "navigation"


def test_detect_intent_comparison():
    """Test intent detection for comparison."""
    assert _detect_intent("Compare Python and Java") == "comparison"
    assert _detect_intent("What's the difference?") == "comparison"
    assert _detect_intent("比较两者的区别") == "comparison"


def test_detect_intent_clarification():
    """Test intent detection for clarification."""
    assert _detect_intent("Explain more") == "clarification"
    assert _detect_intent("Give me more details") == "clarification"
    assert _detect_intent("详细解释一下") == "clarification"


@pytest.mark.asyncio
async def test_is_followup_short_query(sample_session_id, sample_user_id):
    """Test follow-up detection for short queries."""
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="Previous query",
        response="Previous response",
        route="vector",
        entities=[],
    )

    context = get_context(sample_session_id, sample_user_id)
    assert _is_followup_query("More", context) is True
    assert _is_followup_query("Tell me", context) is True


@pytest.mark.asyncio
async def test_is_followup_with_pronouns(sample_session_id, sample_user_id):
    """Test follow-up detection with pronouns."""
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="What is TensorFlow?",
        response="TensorFlow is...",
        route="vector",
        entities=["TensorFlow"],
    )

    context = get_context(sample_session_id, sample_user_id)
    assert _is_followup_query("Tell me more about it", context) is True
    assert _is_followup_query("What are the benefits of this?", context) is True


@pytest.mark.asyncio
async def test_detect_reference_pronouns_chinese(sample_session_id, sample_user_id):
    """Test pronoun detection for Chinese."""
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="Query",
        response="Response",
        route="vector",
        entities=["Python", "Java"],
    )

    context = get_context(sample_session_id, sample_user_id)
    refs = _detect_reference_pronouns("它是什么?", context)
    assert refs is not None
    assert "Python" in refs or "Java" in refs


@pytest.mark.asyncio
async def test_detect_reference_pronouns_english(sample_session_id, sample_user_id):
    """Test pronoun detection for English."""
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="Query",
        response="Response",
        route="vector",
        entities=["TensorFlow"],
    )

    context = get_context(sample_session_id, sample_user_id)
    refs = _detect_reference_pronouns("Tell me about this", context)
    assert refs is not None
    assert "TensorFlow" in refs


@pytest.mark.asyncio
async def test_detect_reference_no_pronouns(sample_session_id, sample_user_id):
    """Test that queries without pronouns return None."""
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="Query",
        response="Response",
        route="vector",
        entities=["Entity"],
    )

    context = get_context(sample_session_id, sample_user_id)
    refs = _detect_reference_pronouns("What is machine learning?", context)
    assert refs is None


@pytest.mark.asyncio
async def test_get_top_entities_empty(sample_session_id, sample_user_id):
    """Test getting top entities from empty mentions."""
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="Query",
        response="Response",
        route="vector",
        entities=[],
    )

    context = get_context(sample_session_id, sample_user_id)
    top = _get_top_entities(context, top_k=3)
    assert len(top) == 0


@pytest.mark.asyncio
async def test_get_top_entities_sorted(sample_session_id, sample_user_id):
    """Test that top entities are sorted by mention count."""
    # Create mentions with different frequencies
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="Q1",
        response="R1",
        route="vector",
        entities=["A", "B", "C"],
    )
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="Q2",
        response="R2",
        route="vector",
        entities=["A", "B"],
    )
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="Q3",
        response="R3",
        route="vector",
        entities=["A"],
    )

    context = get_context(sample_session_id, sample_user_id)
    top = _get_top_entities(context, top_k=3)

    # A should be first (3 mentions), then B (2), then C (1)
    assert top[0] == "A"
    assert top[1] == "B"
    assert top[2] == "C"


# ============================================================================
# Test Admin Functions
# ============================================================================


@pytest.mark.asyncio
async def test_get_all_sessions(sample_user_id):
    """Test getting all active sessions."""
    await update_conversation_context("session-1", sample_user_id, "Q", "R", "vector", [])
    await update_conversation_context("session-2", sample_user_id, "Q", "R", "vector", [])
    await update_conversation_context("session-3", sample_user_id, "Q", "R", "vector", [])

    sessions = get_all_sessions()
    assert len(sessions) == 3
    assert "session-1" in sessions
    assert "session-2" in sessions
    assert "session-3" in sessions


@pytest.mark.asyncio
async def test_get_store_stats(sample_session_id, sample_user_id):
    """Test store statistics."""
    # Add multiple turns
    for i in range(5):
        await update_conversation_context(
            session_id=sample_session_id,
            user_id=sample_user_id,
            query=f"Query {i}",
            response=f"Response {i}",
            route="vector",
            entities=[f"entity{i}"],
        )

    stats = get_store_stats()
    assert stats["active_sessions"] == 1
    assert stats["total_turns"] == 5
    assert stats["total_entities"] == 5  # 5 unique entities


@pytest.mark.asyncio
async def test_topic_stack_deduplication(sample_session_id, sample_user_id):
    """Test that topic stack doesn't duplicate consecutive same routes."""
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="Q1",
        response="R1",
        route="vector",
        entities=[],
    )
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="Q2",
        response="R2",
        route="vector",
        entities=[],
    )
    await update_conversation_context(
        session_id=sample_session_id,
        user_id=sample_user_id,
        query="Q3",
        response="R3",
        route="hybrid",
        entities=[],
    )

    context = get_context(sample_session_id, sample_user_id)
    # Should not duplicate consecutive "vector"
    assert context.topic_stack == ["vector", "hybrid"]


@pytest.mark.asyncio
async def test_topic_stack_size_limit(sample_session_id, sample_user_id):
    """Test that topic stack respects size limit."""
    # Add 7 different routes (limit is 5)
    routes = ["vector", "hybrid", "graph", "react", "vector", "hybrid", "graph"]
    for i, route in enumerate(routes):
        await update_conversation_context(
            session_id=sample_session_id,
            user_id=sample_user_id,
            query=f"Query {i}",
            response=f"Response {i}",
            route=route,
            entities=[],
        )

    context = get_context(sample_session_id, sample_user_id)
    assert len(context.topic_stack) <= 5
    # Should keep the most recent 5
    assert context.topic_stack[-1] == "graph"
