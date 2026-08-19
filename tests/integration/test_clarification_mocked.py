"""Integration tests for clarification flow with mocked LLM calls.

This version uses mocked RouterAgentService to avoid dependency on real LLM API,
making tests faster, more stable, and suitable for CI/CD pipelines.
"""

import pytest
from pathlib import Path
import tempfile
import shutil
from unittest.mock import AsyncMock

from app.agents.router.enhanced_service import EnhancedRouterService
from app.domain.contracts import (
    ClarificationContext,
    RouterAction,
    RouteDecision,
)
from app.orchestration.request import OrchestrationRequest, RequestScope, ConversationTurn
from app.services.sessions.history import HistoryStore


class TestClarificationIntegrationMocked:
    """End-to-end integration tests with mocked LLM calls."""

    @pytest.fixture
    def mock_base_router(self):
        """Create mocked RouterAgentService that returns fake responses."""
        mock_router = AsyncMock()

        # Default mock response for RAG design queries
        mock_router.route.return_value = RouteDecision(
            intent="knowledge_retrieval",
            route="vector",
            confidence=0.95,
            requires_plan=True,
            allowed_capabilities=frozenset(["rag"]),
            reason="Mock response for testing"
        )

        return mock_router

    @pytest.fixture
    def router_service_with_mock(self, mock_base_router):
        """Create EnhancedRouterService with mocked base router."""
        return EnhancedRouterService(base_router=mock_base_router)

    @pytest.fixture
    def temp_session_dir(self):
        """Create temporary directory for session storage."""
        temp_dir = Path(tempfile.mkdtemp())
        yield temp_dir
        shutil.rmtree(temp_dir, ignore_errors=True)

    @pytest.fixture
    def history_store(self, temp_session_dir):
        """Create HistoryStore with temporary directory."""
        return HistoryStore(base_dir=temp_session_dir)

    @pytest.mark.asyncio
    async def test_simple_query_no_clarification_mocked(self, router_service_with_mock):
        """Test that simple queries skip clarification (with mock)."""
        request = OrchestrationRequest(
            question="What is the price of product X in the catalog?",
            session_id="test_mock_1",
            conversation=tuple(),
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        context = ClarificationContext()
        decision = await router_service_with_mock.route(request, context)

        # Simple query should CONTINUE without clarification
        assert decision.action == RouterAction.CONTINUE
        assert decision.clarification is None
        assert decision.context.clarification_round == 0

    @pytest.mark.asyncio
    async def test_complex_query_triggers_clarification_mocked(self, router_service_with_mock):
        """Test that complex queries trigger clarification (with mock)."""
        request = OrchestrationRequest(
            question="帮我设计一个RAG",  # Use Chinese to trigger rag_design intent
            session_id="test_mock_2",
            conversation=tuple(),
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        context = ClarificationContext()
        decision = await router_service_with_mock.route(request, context)

        # Short complex query should trigger clarification
        assert decision.action == RouterAction.NEED_CLARIFICATION
        assert decision.clarification is not None
        assert decision.clarification.field_name in [
            "scenario", "data_source", "scale", "performance_requirement"
        ]
        assert len(decision.clarification.options) > 0
        assert decision.context.intent == "rag_design"
        assert decision.context.max_rounds == 7

    @pytest.mark.asyncio
    async def test_multi_round_clarification_flow_mocked(self, router_service_with_mock):
        """Test complete multi-round clarification flow (with mock)."""
        request = OrchestrationRequest(
            question="帮我搭建RAG",  # Short Chinese query to trigger clarification
            session_id="test_mock_3",
            conversation=tuple(),
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        # Round 1: Initial clarification
        context = ClarificationContext(intent="rag_design", max_rounds=7)
        decision1 = await router_service_with_mock.route(request, context)

        assert decision1.action == RouterAction.NEED_CLARIFICATION
        assert decision1.clarification is not None
        field1 = decision1.clarification.field_name

        # Round 2: Answer first question
        context.collected_info[field1] = "企业知识库"
        context.asked_questions.append(field1)
        context.clarification_round = 1

        decision2 = await router_service_with_mock.route(request, context)

        # Should still need clarification for remaining fields
        assert decision2.action == RouterAction.NEED_CLARIFICATION
        assert decision2.clarification is not None
        field2 = decision2.clarification.field_name
        assert field2 != field1  # Should ask different question

        # Round 3: Answer second question
        context.collected_info[field2] = "PDF文档"
        context.asked_questions.append(field2)
        context.clarification_round = 2

        decision3 = await router_service_with_mock.route(request, context)

        # May continue or need more clarification
        if decision3.action == RouterAction.NEED_CLARIFICATION:
            assert decision3.clarification.field_name not in [field1, field2]

    @pytest.mark.asyncio
    async def test_max_rounds_limit_mocked(self, router_service_with_mock):
        """Test that clarification stops at max rounds (with mock)."""
        request = OrchestrationRequest(
            question="Design a RAG",
            session_id="test_mock_4",
            conversation=tuple(),
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        # Simulate hitting max rounds
        context = ClarificationContext(
            intent="rag_design",
            max_rounds=7,
            clarification_round=7,  # Already at max
            collected_info={},
            asked_questions=[],
        )

        decision = await router_service_with_mock.route(request, context)

        # Should force CONTINUE even with missing info
        assert decision.action == RouterAction.CONTINUE
        assert decision.clarification is None

    @pytest.mark.asyncio
    async def test_all_info_collected_continues_mocked(self, router_service_with_mock):
        """Test that having all required info leads to CONTINUE (with mock)."""
        request = OrchestrationRequest(
            question="Design a RAG system",
            session_id="test_mock_5",
            conversation=tuple(),
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        # Provide all required info for rag_design
        context = ClarificationContext(
            intent="rag_design",
            max_rounds=7,
            collected_info={
                "scenario": "企业知识库",
                "data_source": "PDF文档",
                "scale": "中型（1-10GB）",
                "performance_requirement": "快速（1-3秒）",
            },
            asked_questions=["scenario", "data_source", "scale", "performance_requirement"],
            clarification_round=4,
        )

        decision = await router_service_with_mock.route(request, context)

        # Should CONTINUE since all info is collected
        assert decision.action == RouterAction.CONTINUE
        assert decision.clarification is None

    @pytest.mark.asyncio
    async def test_history_extraction_reduces_rounds_mocked(self, router_service_with_mock):
        """Test that history extraction reduces required clarification rounds (with mock)."""
        # Simulate conversation with context
        conversation = (
            ConversationTurn(role="user", content="I work at a large enterprise company"),
            ConversationTurn(role="assistant", content="How can I help you?"),
            ConversationTurn(role="user", content="We have PDF documents, about 50GB to process"),
        )

        request = OrchestrationRequest(
            question="Help me design a knowledge base system",
            session_id="test_mock_6",
            conversation=conversation,
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        context = ClarificationContext()
        decision = await router_service_with_mock.route(request, context)

        # History should extract: scenario (enterprise), data_source (PDF), scale (50GB)
        # So we should either CONTINUE or need fewer clarifications
        if decision.action == RouterAction.NEED_CLARIFICATION:
            # Should not ask about already known info
            assert decision.clarification.field_name not in ["scenario", "data_source", "scale"]
        else:
            # Or might CONTINUE if enough info extracted
            assert decision.action == RouterAction.CONTINUE

    @pytest.mark.asyncio
    async def test_english_query_with_extraction_mocked(self, router_service_with_mock):
        """Test clarification with English input and extraction (with mock)."""
        request = OrchestrationRequest(
            question="Help me build an enterprise knowledge base with PDF documents, about 50GB, need fast response",
            session_id="test_mock_7",
            conversation=tuple(),
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        context = ClarificationContext()
        decision = await router_service_with_mock.route(request, context)

        # Long question with details should likely CONTINUE
        # (history extraction + long question = sufficient info)
        assert decision.action == RouterAction.CONTINUE

    @pytest.mark.asyncio
    async def test_document_comparison_intent_mocked(self, router_service_with_mock):
        """Test clarification flow for document_comparison intent (with mock)."""
        request = OrchestrationRequest(
            question="比较文档",  # Short Chinese query to trigger clarification
            session_id="test_mock_8",
            conversation=tuple(),
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        context = ClarificationContext()
        decision = await router_service_with_mock.route(request, context)

        # Should trigger clarification for doc comparison
        assert decision.action == RouterAction.NEED_CLARIFICATION
        assert decision.context.intent == "document_comparison"
        assert decision.context.max_rounds == 5
        assert decision.clarification.field_name in ["doc_ids", "comparison_aspect", "output_format"]

    @pytest.mark.asyncio
    async def test_intent_changes_reset_max_rounds_mocked(self, router_service_with_mock):
        """Test that changing intent resets max_rounds dynamically (with mock)."""
        # Start with rag_design intent
        request1 = OrchestrationRequest(
            question="设计RAG",  # Short Chinese to trigger rag_design
            session_id="test_mock_9",
            conversation=tuple(),
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        context = ClarificationContext(intent="rag_design", max_rounds=7)
        decision1 = await router_service_with_mock.route(request1, context)

        # With pre-set context, should maintain rag_design
        assert decision1.context.intent == "rag_design"
        assert decision1.context.max_rounds == 7

        # Change to document comparison (should adjust max_rounds)
        request2 = OrchestrationRequest(
            question="比较文档",  # Short Chinese to trigger document_comparison
            session_id="test_mock_9",
            conversation=tuple(),
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        # Reset context for new intent
        context2 = ClarificationContext()
        decision2 = await router_service_with_mock.route(request2, context2)

        # Intent should change and max_rounds should update
        assert decision2.context.intent == "document_comparison"
        assert decision2.context.max_rounds == 5  # document_comparison max_rounds

    def test_session_persistence_mocked(self, history_store):
        """Test session clarification context persistence (with mock)."""
        session_id = "test_mock_persist_1"

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

        # Retrieve and verify
        context = history_store.get_clarification_context(session_id)
        assert context is not None
        assert context["collected_info"]["scenario"] == "企业知识库"
        assert context["clarification_round"] == 1

    def test_session_reset_mocked(self, history_store):
        """Test session clarification context reset (with mock)."""
        session_id = "test_mock_reset_1"

        # Create and populate
        history_store.create_session(session_id=session_id)
        history_store.update_clarification_context(session_id, "scenario", "企业知识库")
        history_store.update_clarification_context(session_id, "data_source", "PDF文档")

        # Verify populated
        context = history_store.get_clarification_context(session_id)
        assert len(context["collected_info"]) == 2
        assert context["clarification_round"] == 2

        # Reset
        result = history_store.reset_clarification_context(session_id)
        assert result is not None

        # Verify reset
        context = history_store.get_clarification_context(session_id)
        assert len(context["collected_info"]) == 0
        assert len(context["asked_questions"]) == 0
        assert context["clarification_round"] == 0


class TestClarificationEdgeCasesMocked:
    """Edge case tests with mocked LLM calls."""

    @pytest.fixture
    def mock_base_router(self):
        """Create mocked RouterAgentService."""
        mock_router = AsyncMock()
        mock_router.route.return_value = RouteDecision(
            intent="general_qa",
            route="vector",
            confidence=0.80,
            requires_plan=False,
            allowed_capabilities=frozenset(["rag"]),
            reason="Mock response"
        )
        return mock_router

    @pytest.fixture
    def router_service_with_mock(self, mock_base_router):
        """Create EnhancedRouterService with mocked base router."""
        return EnhancedRouterService(base_router=mock_base_router)

    @pytest.mark.asyncio
    async def test_empty_question_mocked(self, router_service_with_mock):
        """Test handling of minimal question (with mock)."""
        # Note: Empty string is rejected by Pydantic validation, so use minimal question
        request = OrchestrationRequest(
            question="?",  # Minimal valid question
            session_id="test_mock_edge_1",
            conversation=tuple(),
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        context = ClarificationContext()
        decision = await router_service_with_mock.route(request, context)

        # Should handle gracefully - likely CONTINUE for general query
        assert decision.action in [RouterAction.CONTINUE, RouterAction.NEED_CLARIFICATION]

    @pytest.mark.asyncio
    async def test_very_long_question_mocked(self, router_service_with_mock):
        """Test handling of very long question (with mock)."""
        long_question = "Design a system " * 100  # 300+ characters

        request = OrchestrationRequest(
            question=long_question,
            session_id="test_mock_edge_2",
            conversation=tuple(),
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        context = ClarificationContext()
        decision = await router_service_with_mock.route(request, context)

        # Long questions should skip clarification
        assert decision.action == RouterAction.CONTINUE

    @pytest.mark.asyncio
    async def test_unicode_characters_mocked(self, router_service_with_mock):
        """Test handling of unicode characters (with mock)."""
        request = OrchestrationRequest(
            question="设计一个RAG系统🚀",
            session_id="test_mock_edge_3",
            conversation=tuple(),
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        context = ClarificationContext()
        decision = await router_service_with_mock.route(request, context)

        # Should handle unicode gracefully
        assert decision.action in [RouterAction.CONTINUE, RouterAction.NEED_CLARIFICATION]

    @pytest.mark.asyncio
    async def test_context_with_empty_collected_info_mocked(self, router_service_with_mock):
        """Test context with empty values in collected_info (with mock)."""
        request = OrchestrationRequest(
            question="设计RAG",  # Short Chinese to trigger rag_design
            session_id="test_mock_edge_4",
            conversation=tuple(),
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        # Context with empty value
        context = ClarificationContext(
            intent="rag_design",
            collected_info={"scenario": ""},  # Empty value
            asked_questions=["scenario"],  # Marked as asked
            clarification_round=1,
            max_rounds=7,
        )

        decision = await router_service_with_mock.route(request, context)

        # Should recognize empty value as missing and ask for remaining fields
        assert decision.action == RouterAction.NEED_CLARIFICATION
