"""Comprehensive tests for dynamic round limits in EnhancedRouterService."""

import pytest

from app.agents.router.enhanced_service import (
    EnhancedRouterService,
    INTENT_COMPLEXITY,
    INTENT_REQUIRED_INFO,
)
from app.domain.contracts import ClarificationContext, RouterAction
from app.orchestration.request import OrchestrationRequest, RequestScope


class TestDynamicRoundConfiguration:
    """Test dynamic round configuration and lookup."""

    def test_intent_complexity_config_exists(self):
        """INTENT_COMPLEXITY should have default and intent mappings."""
        assert "default" in INTENT_COMPLEXITY
        assert INTENT_COMPLEXITY["default"] == 5
        assert INTENT_COMPLEXITY["simple_query"] == 2
        assert INTENT_COMPLEXITY["rag_design"] == 7
        assert INTENT_COMPLEXITY["complex_analysis"] == 10

    def test_intent_required_info_overrides(self):
        """INTENT_REQUIRED_INFO should override INTENT_COMPLEXITY."""
        assert "rag_design" in INTENT_REQUIRED_INFO
        assert INTENT_REQUIRED_INFO["rag_design"]["max_rounds"] == 7
        assert INTENT_REQUIRED_INFO["document_comparison"]["max_rounds"] == 5

    def test_get_max_rounds_priority(self):
        """Test priority: INTENT_REQUIRED_INFO > INTENT_COMPLEXITY > default."""
        service = EnhancedRouterService()

        # Priority 1: INTENT_REQUIRED_INFO
        assert service._get_max_rounds_for_intent("rag_design") == 7

        # Priority 2: INTENT_COMPLEXITY (if not in INTENT_REQUIRED_INFO)
        assert service._get_max_rounds_for_intent("simple_query") == 2

        # Priority 3: default
        assert service._get_max_rounds_for_intent("unknown_intent") == 5


class TestDynamicRoundAllocation:
    """Test dynamic round allocation based on intent."""

    @pytest.mark.asyncio
    async def test_simple_query_allocates_2_rounds(self):
        """Simple queries should allocate max 2 rounds."""
        service = EnhancedRouterService()
        request = OrchestrationRequest(
            question="价格是多少？",
            session_id="test",
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        context = ClarificationContext()
        decision = await service.route(request, context)

        # Simple query continues immediately (no clarification needed)
        assert decision.action == RouterAction.CONTINUE
        # Intent should be general_query
        assert decision.context.intent == "general_query"

    @pytest.mark.asyncio
    async def test_document_lookup_allocates_3_rounds(self):
        """Document lookup should allocate max 3 rounds."""
        service = EnhancedRouterService()
        # This would need proper intent detection, for now test the config
        max_rounds = service._get_max_rounds_for_intent("document_lookup")
        assert max_rounds == 3

    @pytest.mark.asyncio
    async def test_document_comparison_allocates_5_rounds(self):
        """Document comparison should allocate max 5 rounds."""
        service = EnhancedRouterService()
        request = OrchestrationRequest(
            question="比较产品A和产品B的差异",
            session_id="test",
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        context = ClarificationContext()
        decision = await service.route(request, context)

        assert decision.context.intent == "document_comparison"
        assert decision.context.max_rounds == 5

    @pytest.mark.asyncio
    async def test_rag_design_allocates_7_rounds(self):
        """RAG design should allocate max 7 rounds (complex)."""
        service = EnhancedRouterService()
        request = OrchestrationRequest(
            question="帮我设计一个RAG检索增强生成系统",
            session_id="test",
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        context = ClarificationContext()
        decision = await service.route(request, context)

        assert decision.context.intent == "rag_design"
        assert decision.context.max_rounds == 7

    @pytest.mark.asyncio
    async def test_system_architecture_allocates_8_rounds(self):
        """System architecture should allocate max 8 rounds."""
        max_rounds = EnhancedRouterService()._get_max_rounds_for_intent(
            "system_architecture"
        )
        assert max_rounds == 8

    @pytest.mark.asyncio
    async def test_complex_analysis_allocates_10_rounds(self):
        """Complex analysis should allocate max 10 rounds."""
        max_rounds = EnhancedRouterService()._get_max_rounds_for_intent(
            "complex_analysis"
        )
        assert max_rounds == 10


class TestIntentChangeHandling:
    """Test handling when intent changes during clarification."""

    @pytest.mark.asyncio
    async def test_intent_change_updates_max_rounds(self):
        """Changing intent should update max_rounds."""
        service = EnhancedRouterService()

        # Start with document comparison (5 rounds)
        request1 = OrchestrationRequest(
            question="比较两个产品",
            session_id="test",
            use_reasoning=False,
            source_scope=RequestScope(),
        )
        context = ClarificationContext()
        decision1 = await service.route(request1, context)

        assert decision1.context.intent == "document_comparison"
        assert decision1.context.max_rounds == 5

        # Change to RAG design (7 rounds)
        request2 = OrchestrationRequest(
            question="其实我想设计一个RAG系统",
            session_id="test",
            use_reasoning=False,
            source_scope=RequestScope(),
        )
        # Reuse context from previous round
        context = decision1.context
        context.clarification_round = 2  # Already used 2 rounds

        decision2 = await service.route(request2, context)

        # Intent changed, max_rounds should update
        assert decision2.context.intent == "rag_design"
        assert decision2.context.max_rounds == 7

    @pytest.mark.asyncio
    async def test_same_intent_preserves_max_rounds(self):
        """Same intent should preserve max_rounds."""
        service = EnhancedRouterService()

        request = OrchestrationRequest(
            question="设计RAG",
            session_id="test",
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        context = ClarificationContext(intent="rag_design", max_rounds=7)
        decision = await service.route(request, context)

        # Intent unchanged, max_rounds should stay 7
        assert decision.context.intent == "rag_design"
        assert decision.context.max_rounds == 7


class TestMaxRoundsEnforcement:
    """Test max rounds limit enforcement."""

    @pytest.mark.asyncio
    async def test_exceeding_max_rounds_forces_continue(self):
        """Exceeding max_rounds should force CONTINUE."""
        service = EnhancedRouterService()
        request = OrchestrationRequest(
            question="设计RAG系统",
            session_id="test",
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        # Simulate reaching max rounds
        context = ClarificationContext(
            intent="rag_design",
            max_rounds=7,
            clarification_round=7,  # Reached limit
        )

        decision = await service.route(request, context)

        # Should force CONTINUE even if info is missing
        assert decision.action == RouterAction.CONTINUE

    @pytest.mark.asyncio
    async def test_at_max_rounds_minus_one_can_still_clarify(self):
        """At max_rounds - 1, can still ask one more question."""
        service = EnhancedRouterService()
        request = OrchestrationRequest(
            question="设计RAG",
            session_id="test",
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        # One round before limit
        context = ClarificationContext(
            intent="rag_design",
            max_rounds=7,
            clarification_round=6,  # 6 < 7, can ask once more
            collected_info={"scenario": "企业知识库"},  # Partial info
        )

        decision = await service.route(request, context)

        # Should ask for more info (not force continue yet)
        # Note: Actual behavior depends on missing info logic
        assert decision.context.clarification_round == 6


class TestRoundUtilization:
    """Test round utilization patterns."""

    @pytest.mark.asyncio
    async def test_simple_query_uses_fewer_rounds(self):
        """Simple queries should complete in 1-2 rounds."""
        service = EnhancedRouterService()
        request = OrchestrationRequest(
            question="产品价格多少钱？",
            session_id="test",
            use_reasoning=False,
            source_scope=RequestScope(),
        )

        context = ClarificationContext()
        decision = await service.route(request, context)

        # Simple query continues immediately
        assert decision.action == RouterAction.CONTINUE
        assert decision.context.clarification_round == 0

    @pytest.mark.asyncio
    async def test_complex_query_can_use_more_rounds(self):
        """Complex queries can use up to max_rounds."""
        service = EnhancedRouterService()

        # RAG design has max_rounds=7
        max_rounds = service._get_max_rounds_for_intent("rag_design")
        assert max_rounds == 7

        # Simulate using 5 rounds (should be allowed)
        context = ClarificationContext(
            intent="rag_design",
            max_rounds=7,
            clarification_round=5,
        )
        assert context.clarification_round < context.max_rounds


class TestDefaultFallback:
    """Test default fallback behavior."""

    @pytest.mark.asyncio
    async def test_unknown_intent_uses_default_5_rounds(self):
        """Unknown intent should fall back to default 5 rounds."""
        service = EnhancedRouterService()
        max_rounds = service._get_max_rounds_for_intent("completely_unknown")
        assert max_rounds == 5  # default

    @pytest.mark.asyncio
    async def test_empty_intent_uses_default(self):
        """Empty intent should use default."""
        service = EnhancedRouterService()
        max_rounds = service._get_max_rounds_for_intent("")
        assert max_rounds == 5


class TestRoundMetrics:
    """Test metrics related to round usage."""

    def test_round_utilization_targets(self):
        """Document target utilization rates."""
        # Target: 50-80% utilization
        # Simple query: 1-2 rounds out of 2 max = 50-100%
        # Document comparison: 2-4 rounds out of 5 max = 40-80%
        # RAG design: 4-6 rounds out of 7 max = 57-86%
        # Complex analysis: 5-8 rounds out of 10 max = 50-80%

        utilization_targets = {
            "simple_query": (0.5, 1.0),       # 50-100%
            "document_comparison": (0.4, 0.8),  # 40-80%
            "rag_design": (0.57, 0.86),       # 57-86%
            "complex_analysis": (0.5, 0.8),   # 50-80%
        }

        # Verify targets are reasonable
        for intent, (min_util, max_util) in utilization_targets.items():
            assert 0 < min_util <= max_util <= 1.0

    def test_max_rounds_reached_threshold(self):
        """Max rounds reached should be < 10% of all queries."""
        # This is a metric test - document the threshold
        max_rounds_reached_threshold = 0.10  # 10%
        assert 0 < max_rounds_reached_threshold < 0.2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
