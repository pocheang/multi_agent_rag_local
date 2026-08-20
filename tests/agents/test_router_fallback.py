"""Tests for router agent fallback strategies."""
import pytest
from unittest.mock import Mock, patch
from app.agents.router.routing import decide_route, LegacyRouteDecision as RouteDecision
from app.agents.shared.config import (
    ROUTE_VECTOR,
    AGENT_CLASS_GENERAL,
    SKILL_DEFAULT,
)
from app.agents.shared.cache import clear_agent_caches


@pytest.fixture(autouse=True)
def clear_router_cache():
    """Keep mocked routing decisions isolated from the process-wide cache."""
    clear_agent_caches()
    yield
    clear_agent_caches()


class TestFallbackDetection:
    """Test low-confidence detection and fallback triggering."""

    def test_low_confidence_triggers_fallback(self):
        """Test that confidence < threshold triggers fallback."""
        # Mock LLM to return low confidence decision
        with patch("app.agents.router.routing.get_chat_model") as mock_model:
            mock_response = Mock()
            mock_response.content = '{"route":"graph","reason":"uncertain","skill":"answer_with_citations","confidence":0.45}'
            mock_model.return_value.invoke.return_value = mock_response

            decision = decide_route("ambiguous query")

            # Should fallback to safe route (vector)
            assert decision.route == ROUTE_VECTOR
            assert "fallback" in decision.reason.lower()

    def test_medium_confidence_no_fallback(self):
        """Test that confidence >= threshold does not trigger fallback."""
        with patch("app.agents.router.routing.get_chat_model") as mock_model:
            mock_response = Mock()
            mock_response.content = '{"route":"graph","reason":"clear entity query","skill":"answer_with_citations","confidence":0.75}'
            mock_model.return_value.invoke.return_value = mock_response

            decision = decide_route("What is entity X?")

            # Should keep original decision
            assert decision.route == "graph"
            assert "fallback" not in decision.reason.lower()

    def test_high_confidence_no_fallback(self):
        """Test that high confidence does not trigger fallback."""
        with patch("app.agents.router.routing.get_chat_model") as mock_model:
            mock_response = Mock()
            mock_response.content = '{"route":"hybrid","reason":"complex query","skill":"compare_entities","confidence":0.92}'
            mock_model.return_value.invoke.return_value = mock_response

            decision = decide_route("Compare A and B")

            # Should keep original decision
            assert decision.route == "hybrid"
            assert "fallback" not in decision.reason.lower()


class TestFallbackStrategy:
    """Test fallback strategy execution."""

    def test_fallback_tries_reasoning_model(self):
        """Test that fallback tries reasoning model on low confidence."""
        with patch("app.agents.router.routing.get_chat_model") as mock_chat:
            with patch("app.agents.router.routing.get_reasoning_model") as mock_reasoning:
                # First call (chat model) returns low confidence
                mock_chat_response = Mock()
                mock_chat_response.content = '{"route":"graph","reason":"uncertain","skill":"answer_with_citations","confidence":0.45}'
                mock_chat.return_value.invoke.return_value = mock_chat_response

                # Second call (reasoning model) returns higher confidence
                mock_reasoning_response = Mock()
                mock_reasoning_response.content = '{"route":"vector","reason":"clear concept query","skill":"answer_with_citations","confidence":0.80}'
                mock_reasoning.return_value.invoke.return_value = mock_reasoning_response

                decision = decide_route("What is X?")

                # Should use reasoning model result
                assert decision.route == ROUTE_VECTOR
                assert "fallback_reasoning" in decision.reason

    def test_fallback_to_safe_route_when_reasoning_fails(self):
        """Test that fallback defaults to vector when reasoning model also fails."""
        with patch("app.agents.router.routing.get_chat_model") as mock_chat:
            with patch("app.agents.router.routing.get_reasoning_model") as mock_reasoning:
                with patch("app.agents.router.routing._calibrator", None):  # Disable calibration
                    # First call returns low confidence
                    mock_chat_response = Mock()
                    mock_chat_response.content = '{"route":"graph","reason":"uncertain","skill":"answer_with_citations","confidence":0.45}'
                    mock_chat.return_value.invoke.return_value = mock_chat_response

                    # Reasoning model also returns low confidence (below threshold)
                    mock_reasoning_response = Mock()
                    mock_reasoning_response.content = '{"route":"hybrid","reason":"still uncertain","skill":"answer_with_citations","confidence":0.55}'
                    mock_reasoning.return_value.invoke.return_value = mock_reasoning_response

                    decision = decide_route("ambiguous query")

                    # Should default to safe route (vector)
                    assert decision.route == ROUTE_VECTOR
                    # Reason should indicate fallback was used (either safe route or reasoning)
                    assert "fallback" in decision.reason.lower()

    def test_fallback_when_reasoning_model_throws_exception(self):
        """Test fallback handles reasoning model exceptions gracefully."""
        with patch("app.agents.router.routing.get_chat_model") as mock_chat:
            with patch("app.agents.router.routing.get_reasoning_model") as mock_reasoning:
                # First call returns low confidence
                mock_chat_response = Mock()
                mock_chat_response.content = '{"route":"graph","reason":"uncertain","skill":"answer_with_citations","confidence":0.45}'
                mock_chat.return_value.invoke.return_value = mock_chat_response

                # Reasoning model throws exception
                mock_reasoning.return_value.invoke.side_effect = Exception("Model error")

                decision = decide_route("test query")

                # Should fallback to safe route
                assert decision.route == ROUTE_VECTOR
                assert "fallback" in decision.reason.lower()


class TestAmbiguousQueryDetection:
    """Test detection of ambiguous queries."""

    def test_detect_ambiguous_with_similar_confidence_scores(self):
        """Test detection when multiple routes have similar scores."""
        # This would require returning multiple route scores from LLM
        # For now, we detect ambiguity via low confidence
        with patch("app.agents.router.routing.get_chat_model") as mock_model:
            mock_response = Mock()
            # Low confidence indicates ambiguity
            mock_response.content = '{"route":"hybrid","reason":"could be vector or graph","skill":"answer_with_citations","confidence":0.52}'
            mock_model.return_value.invoke.return_value = mock_response

            decision = decide_route("unclear query")

            # Should trigger fallback due to low confidence
            assert decision.route == ROUTE_VECTOR
            assert "fallback" in decision.reason.lower()

    def test_clear_query_not_ambiguous(self):
        """Test that clear queries are not marked as ambiguous."""
        with patch("app.agents.router.routing.get_chat_model") as mock_model:
            with patch("app.agents.router.routing._calibrator", None):  # Disable calibration
                mock_response = Mock()
                mock_response.content = '{"route":"vector","reason":"clear definition query","skill":"answer_with_citations","confidence":0.88}'
                mock_model.return_value.invoke.return_value = mock_response

                decision = decide_route("What is machine learning?")

                # Should not trigger fallback
                assert "fallback" not in decision.reason.lower()
                assert decision.confidence >= 0.6


class TestFallbackLogging:
    """Test fallback event logging."""

    def test_fallback_event_logged(self, caplog):
        """Test that fallback events are logged for analysis."""
        import logging

        # Set log level for the router agent module
        logger = logging.getLogger('app.agents.router.routing')
        logger.setLevel(logging.INFO)
        caplog.set_level(logging.INFO, logger='app.agents.router.routing')

        with patch("app.agents.router.routing.get_chat_model") as mock_chat:
            with patch("app.agents.router.routing.get_reasoning_model") as mock_reasoning:
                # Low confidence triggers fallback
                mock_chat_response = Mock()
                mock_chat_response.content = '{"route":"graph","reason":"uncertain","skill":"answer_with_citations","confidence":0.48}'
                mock_chat.return_value.invoke.return_value = mock_chat_response

                # Reasoning model provides better result
                mock_reasoning_response = Mock()
                mock_reasoning_response.content = '{"route":"vector","reason":"concept query","skill":"answer_with_citations","confidence":0.75}'
                mock_reasoning.return_value.invoke.return_value = mock_reasoning_response

                decision = decide_route("test query")

                # Check that fallback was logged (either in message or in reason)
                log_messages = [record.message for record in caplog.records]
                # Also check the decision reason for fallback marker
                assert any("fallback" in msg.lower() for msg in log_messages) or "fallback" in decision.reason.lower(), \
                    f"No fallback indicator found. Logs: {log_messages}, Reason: {decision.reason}"

    def test_no_fallback_logging_for_high_confidence(self, caplog):
        """Test that no fallback logging occurs for high confidence."""
        import logging
        caplog.set_level(logging.INFO)

        with patch("app.agents.router.routing.get_chat_model") as mock_model:
            mock_response = Mock()
            mock_response.content = '{"route":"vector","reason":"clear query","skill":"answer_with_citations","confidence":0.85}'
            mock_model.return_value.invoke.return_value = mock_response

            decision = decide_route("What is X?")

            # No fallback logging
            fallback_logs = [r for r in caplog.records if "fallback" in r.message.lower()]
            assert len(fallback_logs) == 0


class TestConfigurableThreshold:
    """Test that fallback threshold is configurable."""

    def test_threshold_from_config(self):
        """Test that threshold is read from agent_config."""
        from app.agents.shared.config import ROUTER_LOW_CONFIDENCE_THRESHOLD

        # Should be defined in config
        assert hasattr(ROUTER_LOW_CONFIDENCE_THRESHOLD, '__class__')
        assert isinstance(ROUTER_LOW_CONFIDENCE_THRESHOLD, float)
        assert 0.0 < ROUTER_LOW_CONFIDENCE_THRESHOLD < 1.0

    def test_fallback_uses_configured_threshold(self):
        """Test that fallback logic uses the configured threshold."""
        with patch("app.agents.router.routing.get_chat_model") as mock_model:
            # Return confidence just below threshold (0.6)
            mock_response = Mock()
            mock_response.content = '{"route":"graph","reason":"uncertain","skill":"answer_with_citations","confidence":0.59}'
            mock_model.return_value.invoke.return_value = mock_response

            decision = decide_route("test query")

            # Should trigger fallback
            assert "fallback" in decision.reason.lower()


class TestFallbackImprovesHandling:
    """Test that fallback improves handling of ambiguous queries."""

    def test_ambiguous_query_handling_improvement(self):
        """Test that fallback provides a safe default for ambiguous queries."""
        ambiguous_queries = [
            "Tell me about it",  # Ambiguous reference
            "What do you think?",  # Opinion question
            "Can you help with something?",  # Vague request
            "Is this good or bad?",  # Context-dependent
        ]

        for query in ambiguous_queries:
            with patch("app.agents.router.routing.get_chat_model") as mock_model:
                # Return low confidence for ambiguous queries
                mock_response = Mock()
                mock_response.content = '{"route":"hybrid","reason":"unclear","skill":"answer_with_citations","confidence":0.40}'
                mock_model.return_value.invoke.return_value = mock_response

                decision = decide_route(query)

                # Should fallback to safe route
                assert decision.route == ROUTE_VECTOR, f"Failed for query: {query}"
                assert "fallback" in decision.reason.lower(), f"No fallback for query: {query}"

    def test_clear_query_no_unnecessary_fallback(self):
        """Test that clear queries don't trigger unnecessary fallback."""
        clear_queries = [
            "What is machine learning?",
            "Define neural networks",
            "Explain reinforcement learning",
        ]

        for query in clear_queries:
            with patch("app.agents.router.routing.get_chat_model") as mock_model:
                with patch("app.agents.router.routing._calibrator", None):  # Disable calibration
                    # Return high confidence for clear queries
                    mock_response = Mock()
                    mock_response.content = '{"route":"vector","reason":"clear definition query","skill":"answer_with_citations","confidence":0.85}'
                    mock_model.return_value.invoke.return_value = mock_response

                    decision = decide_route(query)

                    # Should not trigger fallback
                    assert "fallback" not in decision.reason.lower(), f"Unnecessary fallback for: {query}"
                    assert decision.confidence >= 0.6, f"Confidence too low for: {query}"


class TestBackwardCompatibility:
    """Test backward compatibility of fallback implementation."""

    def test_existing_api_unchanged(self):
        """Test that decide_route signature is unchanged."""
        with patch("app.agents.router.routing.get_chat_model") as mock_model:
            mock_response = Mock()
            mock_response.content = '{"route":"vector","reason":"test","skill":"answer_with_citations","confidence":0.75}'
            mock_model.return_value.invoke.return_value = mock_response

            # Should work with existing parameters
            decision = decide_route("test query")
            assert isinstance(decision, RouteDecision)

            decision = decide_route("test", use_reasoning=True)
            assert isinstance(decision, RouteDecision)

            decision = decide_route("test", agent_class_hint="general")
            assert isinstance(decision, RouteDecision)

    def test_route_decision_has_required_fields(self):
        """Test that RouteDecision maintains required fields."""
        with patch("app.agents.router.routing.get_chat_model") as mock_model:
            mock_response = Mock()
            mock_response.content = '{"route":"vector","reason":"test","skill":"answer_with_citations","confidence":0.75}'
            mock_model.return_value.invoke.return_value = mock_response

            decision = decide_route("test query")

            # All existing fields must be present
            assert hasattr(decision, "route")
            assert hasattr(decision, "reason")
            assert hasattr(decision, "skill")
            assert hasattr(decision, "agent_class")
            assert hasattr(decision, "confidence")


class TestEnglishAndChineseQueries:
    """Test fallback works for both English and Chinese queries."""

    def test_fallback_handles_chinese_query(self):
        """Test that fallback works for Chinese queries."""
        with patch("app.agents.router.routing.get_chat_model") as mock_model:
            mock_response = Mock()
            # Low confidence for Chinese query
            mock_response.content = '{"route":"graph","reason":"不确定","skill":"answer_with_citations","confidence":0.45}'
            mock_model.return_value.invoke.return_value = mock_response

            decision = decide_route("这是什么？")  # "What is this?"

            # Should trigger fallback
            assert decision.route == ROUTE_VECTOR
            assert "fallback" in decision.reason.lower()

    def test_fallback_handles_english_query(self):
        """Test that fallback works for English queries."""
        with patch("app.agents.router.routing.get_chat_model") as mock_model:
            mock_response = Mock()
            mock_response.content = '{"route":"hybrid","reason":"uncertain","skill":"answer_with_citations","confidence":0.50}'
            mock_model.return_value.invoke.return_value = mock_response

            decision = decide_route("What is this?")

            # Should trigger fallback
            assert decision.route == ROUTE_VECTOR
            assert "fallback" in decision.reason.lower()
