"""Integration tests for the complete clarification flow.

Tests the end-to-end clarification mechanism including:
- EnhancedRouterService
- ClarificationContext persistence
- Session management
- Multi-round clarification
"""

import pytest
from pathlib import Path
import tempfile
import shutil

from app.agents.router.enhanced_service import EnhancedRouterService
from app.domain.contracts import ClarificationContext, RouterAction
from app.orchestration.request import OrchestrationRequest, RequestScope, ConversationTurn
from app.services.sessions.history import HistoryStore


class TestClarificationIntegration:
    """End-to-end integration tests for clarification flow."""

    @pytest.fixture
    def temp_session_dir(self):
        """Create temporary directory for session storage."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        # Cleanup after test
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def history_store(self, temp_session_dir):
        """Create HistoryStore with temporary directory."""
        return HistoryStore(base_dir=temp_session_dir)

    @pytest.fixture
    def router_service(self):
        """Create EnhancedRouterService instance."""
        return EnhancedRouterService()

    @pytest.mark.asyncio
    async def test_simple_query_no_clarification(self, router_service):
        """Test that simple queries skip clarification."""
        request = OrchestrationRequest(
            question="What is the price of product X in the catalog?",
            session_id="test_session_1",
            conversation=tuple(),
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        context = ClarificationContext()
        decision = await router_service.route(request, context)

        assert decision.action == RouterAction.CONTINUE
        assert decision.clarification is None
        assert decision.context.clarification_round == 0

    @pytest.mark.asyncio
    async def test_complex_query_triggers_clarification(self, router_service):
        """Test that complex queries trigger clarification."""
        request = OrchestrationRequest(
            question="Design a RAG system",
            session_id="test_session_2",
            conversation=tuple(),
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        context = ClarificationContext()
        decision = await router_service.route(request, context)

        assert decision.action == RouterAction.NEED_CLARIFICATION
        assert decision.clarification is not None
        assert decision.clarification.field_name in ["scenario", "data_source", "scale", "performance_requirement"]
        assert len(decision.clarification.options) > 0

    def test_session_clarification_context_persistence(self, history_store):
        """Test that clarification context persists in session."""
        session_id = "test_persist_1"

        # Create session
        session = history_store.create_session(session_id=session_id)
        assert "clarification_context" in session

        # Update clarification context
        result = history_store.update_clarification_context(
            session_id,
            "scenario",
            "企业知识库"
        )

        assert result is not None
        assert result["clarification_context"]["collected_info"]["scenario"] == "企业知识库"
        assert "scenario" in result["clarification_context"]["asked_questions"]
        assert result["clarification_context"]["clarification_round"] == 1

        # Retrieve context
        context = history_store.get_clarification_context(session_id)
        assert context is not None
        assert context["collected_info"]["scenario"] == "企业知识库"

    def test_session_clarification_context_reset(self, history_store):
        """Test resetting clarification context."""
        session_id = "test_reset_1"

        # Create and populate context
        history_store.create_session(session_id=session_id)
        history_store.update_clarification_context(session_id, "scenario", "企业知识库")
        history_store.update_clarification_context(session_id, "data_source", "PDF文档")

        # Verify populated
        context = history_store.get_clarification_context(session_id)
        assert len(context["collected_info"]) == 2

        # Reset
        result = history_store.reset_clarification_context(session_id)
        assert result is not None

        # Verify reset
        context = history_store.get_clarification_context(session_id)
        assert len(context["collected_info"]) == 0
        assert len(context["asked_questions"]) == 0
        assert context["clarification_round"] == 0
