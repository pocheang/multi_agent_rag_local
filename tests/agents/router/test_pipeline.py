"""
Unit tests for router pipeline components.

Tests each component independently to ensure single-responsibility and testability.
"""

import pytest

from app.agents.router.pipeline import (
    IntentClassifier,
    SkillSelector,
    RouteDecider,
    FallbackHandler,
    RoutingPipeline,
    Intent,
    Skill,
    RouteCandidate,
    FinalRoute,
)


# ============================================================================
# Intent Classifier Tests
# ============================================================================

class TestIntentClassifier:
    """Test intent classification logic."""

    def test_forced_hint_valid(self):
        """Should accept valid forced hint."""
        classifier = IntentClassifier()
        result = classifier.classify("test", forced_hint="cybersecurity")

        assert result.type == "cybersecurity"
        assert result.confidence == 1.0
        assert result.method == "forced"

    def test_forced_hint_invalid(self):
        """Should fallback to general for invalid hint."""
        classifier = IntentClassifier()
        result = classifier.classify("test", forced_hint="invalid_class")

        assert result.type == "general"
        assert result.confidence == 0.5
        assert result.method == "forced_invalid"

    def test_smalltalk_detection(self):
        """Should detect smalltalk queries."""
        classifier = IntentClassifier()
        result = classifier.classify("你好", use_llm=False)

        assert result.type == "smalltalk"
        assert result.confidence == 0.95
        assert result.method == "rule_based_smalltalk"

    def test_rule_based_fallback(self):
        """Should use rule-based classification when LLM disabled."""
        classifier = IntentClassifier()
        result = classifier.classify("什么是网络安全？", use_llm=False)

        assert result.type in ["general", "cybersecurity"]
        assert result.confidence == 0.5
        assert result.method == "rule_based"


# ============================================================================
# Skill Selector Tests
# ============================================================================

class TestSkillSelector:
    """Test skill selection logic."""

    def test_cybersecurity_skill(self):
        """Should select cyber skill for cybersecurity intent."""
        selector = SkillSelector()
        intent = Intent(type="cybersecurity", confidence=0.8, method="llm")

        result = selector.select("什么是XSS攻击？", intent)

        assert result.source == "agent_class_cybersecurity"
        assert result.name in ["cyber_attack_analysis", "cyber_defense_hardening", "incident_response_playbook"]

    def test_pdf_skill(self):
        """Should select PDF reader for pdf_text intent."""
        selector = SkillSelector()
        intent = Intent(type="pdf_text", confidence=0.9, method="llm")

        result = selector.select("PDF内容是什么？", intent)

        assert result.name == "pdf_text_reader"
        assert result.source == "agent_class_pdf"

    def test_compare_pattern(self):
        """Should detect compare queries."""
        selector = SkillSelector()
        intent = Intent(type="general", confidence=0.7, method="llm")

        result = selector.select("compare A and B difference", intent)

        assert result.name == "compare_entities"
        assert result.source == "query_pattern_compare"

    def test_timeline_pattern(self):
        """Should detect timeline queries."""
        selector = SkillSelector()
        intent = Intent(type="general", confidence=0.7, method="llm")

        result = selector.select("company history timeline", intent)

        assert result.name == "timeline_builder"
        assert result.source == "query_pattern_timeline"

    def test_default_skill(self):
        """Should use default skill when no pattern matches."""
        selector = SkillSelector()
        intent = Intent(type="general", confidence=0.7, method="llm")

        result = selector.select("普通问题", intent)

        assert result.name == "answer_with_citations"
        assert result.source == "default"


# ============================================================================
# Route Decider Tests
# ============================================================================

class TestRouteDecider:
    """Test route decision logic."""

    @pytest.mark.integration
    def test_decide_with_valid_response(self):
        """Should parse valid LLM response."""
        from app.prompts import build_router_prompt
        from app.agents.router.examples import get_mixed_examples

        prompt = build_router_prompt(get_mixed_examples())
        decider = RouteDecider(prompt)

        intent = Intent(type="general", confidence=0.8, method="llm")
        skill = Skill(name="general_qa", source="default")

        result = decider.decide("什么是机器学习？", intent, skill, use_reasoning=False)

        assert result.route in ["vector", "graph", "hybrid", "react"]
        assert 0.0 <= result.confidence <= 1.0
        assert result.reason
        assert result.skill == skill
        assert result.agent_class == "general"

    def test_json_extraction_valid(self):
        """Should extract JSON from response."""
        from app.prompts import build_router_prompt
        from app.agents.router.examples import get_mixed_examples

        prompt = build_router_prompt(get_mixed_examples())
        decider = RouteDecider(prompt)

        text = '{"route": "vector", "confidence": 0.85, "reason": "test"}'
        result = decider._extract_json(text)

        assert result["route"] == "vector"
        assert result["confidence"] == 0.85
        assert result["reason"] == "test"

    def test_json_extraction_malformed(self):
        """Should handle malformed JSON."""
        from app.prompts import build_router_prompt
        from app.agents.router.examples import get_mixed_examples

        prompt = build_router_prompt(get_mixed_examples())
        decider = RouteDecider(prompt)

        text = "invalid json {route: vector"
        result = decider._extract_json(text)

        assert result["route"] == "vector"
        assert "fallback" in result["reason"]

    def test_route_normalization(self):
        """Should normalize and validate routes."""
        from app.prompts import build_router_prompt
        from app.agents.router.examples import get_mixed_examples

        prompt = build_router_prompt(get_mixed_examples())
        decider = RouteDecider(prompt)

        assert decider._normalize_route("VECTOR") == "vector"
        assert decider._normalize_route("invalid") == "vector"
        assert decider._normalize_route("graph") == "graph"


# ============================================================================
# Fallback Handler Tests
# ============================================================================

class TestFallbackHandler:
    """Test fallback handling logic."""

    def test_high_confidence_no_fallback(self):
        """Should not trigger fallback for high confidence."""
        handler = FallbackHandler()

        candidate = RouteCandidate(
            route="vector",
            confidence=0.9,
            reason="test",
            skill=Skill(name="answer_with_citations", source="default"),
            agent_class="general",
        )

        result = handler.handle("test question", candidate, threshold=0.6)

        assert result == candidate

    @pytest.mark.skip(reason="Requires LLM call to reasoning model")
    def test_low_confidence_fallback_safe_route(self):
        """Should fall back to safe route for low confidence."""
        handler = FallbackHandler()

        candidate = RouteCandidate(
            route="react",
            confidence=0.4,
            reason="uncertain",
            skill=Skill(name="answer_with_citations", source="default"),
            agent_class="general",
        )

        result = handler.handle("test question", candidate, threshold=0.6)

        assert result.route == "vector"  # Safe fallback
        assert result.confidence >= 0.5
        assert "fallback_safe_route" in result.reason


# ============================================================================
# Pipeline Integration Tests
# ============================================================================

class TestRoutingPipeline:
    """Test complete routing pipeline."""

    def test_pipeline_initialization(self):
        """Should initialize with default components."""
        pipeline = RoutingPipeline()

        assert pipeline.intent_classifier is not None
        assert pipeline.skill_selector is not None
        assert pipeline.route_decider is not None
        assert pipeline.fallback_handler is not None

    def test_pipeline_custom_components(self):
        """Should accept custom components."""
        custom_classifier = IntentClassifier()

        pipeline = RoutingPipeline(intent_classifier=custom_classifier)

        assert pipeline.intent_classifier == custom_classifier

    @pytest.mark.integration
    def test_pipeline_end_to_end(self):
        """Should execute complete pipeline."""
        pipeline = RoutingPipeline()

        result = pipeline.decide("什么是机器学习？", use_reasoning=False)

        assert isinstance(result, FinalRoute)
        assert result.route in ["vector", "graph", "hybrid", "react"]
        assert result.skill
        assert result.agent_class
        assert 0.0 <= result.confidence <= 1.0
        assert result.reason

    @pytest.mark.integration
    def test_pipeline_with_forced_intent(self):
        """Should respect forced agent class."""
        pipeline = RoutingPipeline()

        result = pipeline.decide(
            "什么是XSS？",
            agent_class_hint="cybersecurity",
        )

        assert result.agent_class == "cybersecurity"

    @pytest.mark.integration
    def test_pipeline_smalltalk(self):
        """Should handle smalltalk queries."""
        pipeline = RoutingPipeline()

        result = pipeline.decide("你好", use_llm_intent=False)

        assert result.route == "vector"
        assert result.agent_class == "smalltalk"

    @pytest.mark.integration
    def test_pipeline_with_reasoning(self):
        """Should use reasoning model when requested."""
        pipeline = RoutingPipeline()

        result = pipeline.decide(
            "复杂的多步骤推理问题",
            use_reasoning=True,
        )

        assert isinstance(result, FinalRoute)


# ============================================================================
# Component Comparison Tests
# ============================================================================

class TestComponentArchitecture:
    """Test that refactored architecture maintains correctness."""

    @pytest.mark.integration
    def test_refactored_vs_legacy_simple_query(self):
        """Should produce similar results to legacy implementation."""
        from app.agents.router.routing import decide_route as legacy_decide

        pipeline = RoutingPipeline()

        question = "什么是机器学习？"

        legacy_result = legacy_decide(question, use_reasoning=False)
        refactored_result = pipeline.decide(question, use_reasoning=False)

        # Routes should match (both should choose appropriate route)
        assert refactored_result.route in ["vector", "graph", "hybrid"]

        # Agent class should match
        assert refactored_result.agent_class == legacy_result.agent_class

        # Both should have reasonable confidence
        assert refactored_result.confidence > 0.0
        assert legacy_result.confidence > 0.0
