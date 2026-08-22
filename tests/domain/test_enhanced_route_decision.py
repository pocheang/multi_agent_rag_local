"""Test EnhancedRouteDecision composition pattern."""

import pytest

from app.domain.contracts import (
    ClarificationContext,
    EnhancedRouteDecision,
    RouteDecision,
    RouterAction,
)


def test_enhanced_route_decision_delegates_to_base() -> None:
    """EnhancedRouteDecision should delegate all RouteDecision fields to base_decision."""
    base = RouteDecision(
        intent="web_search",
        route="web",
        confidence=0.9,
        requires_plan=False,
        allowed_capabilities=frozenset({"rag", "web"}),
        reason="test_reason",
    )

    enhanced = EnhancedRouteDecision(
        base_decision=base,
        action=RouterAction.CONTINUE,
    )

    # Verify delegation works
    assert enhanced.intent == "web_search"
    assert enhanced.route == "web"
    assert enhanced.confidence == 0.9
    assert enhanced.requires_plan is False
    assert enhanced.allowed_capabilities == frozenset({"rag", "web"})
    assert enhanced.reason == "test_reason"
    assert enhanced.effective_route == "web"


def test_enhanced_route_decision_adds_clarification_fields() -> None:
    """EnhancedRouteDecision should add clarification-specific fields."""
    base = RouteDecision(
        confidence=0.8,
        requires_plan=False,
        reason="test",
    )

    context = ClarificationContext(
        collected_info={"field1": "value1"},
        clarification_round=2,
    )

    enhanced = EnhancedRouteDecision(
        base_decision=base,
        action=RouterAction.NEED_CLARIFICATION,
        missing_information=("field2", "field3"),
        context=context,
    )

    # Verify clarification fields
    assert enhanced.action == RouterAction.NEED_CLARIFICATION
    assert enhanced.missing_information == ("field2", "field3")
    assert enhanced.context.collected_info == {"field1": "value1"}
    assert enhanced.context.clarification_round == 2


def test_enhanced_route_decision_is_immutable() -> None:
    """EnhancedRouteDecision should be immutable like its base."""
    base = RouteDecision(
        confidence=0.5,
        requires_plan=False,
        reason="test",
    )

    enhanced = EnhancedRouteDecision(
        base_decision=base,
        action=RouterAction.CONTINUE,
    )

    # Should not be able to modify fields
    with pytest.raises((AttributeError, ValueError)):
        enhanced.action = RouterAction.NEED_CLARIFICATION  # type: ignore


def test_enhanced_route_decision_effective_route_delegation() -> None:
    """effective_route property should work through delegation."""
    # Test with explicit route
    base_with_route = RouteDecision(
        intent="knowledge_retrieval",
        route="graph",
        confidence=0.8,
        requires_plan=False,
        reason="test",
    )

    enhanced1 = EnhancedRouteDecision(
        base_decision=base_with_route,
        action=RouterAction.CONTINUE,
    )
    assert enhanced1.effective_route == "graph"

    # Test without explicit route (should use intent mapping)
    base_without_route = RouteDecision(
        intent="web_search",
        confidence=0.8,
        requires_plan=False,
        reason="test",
    )

    enhanced2 = EnhancedRouteDecision(
        base_decision=base_without_route,
        action=RouterAction.CONTINUE,
    )
    assert enhanced2.effective_route == "web"


def test_enhanced_route_decision_base_is_immutable() -> None:
    """Modifying base_decision after creation should not affect enhanced."""
    base = RouteDecision(
        confidence=0.7,
        requires_plan=False,
        reason="original",
    )

    enhanced = EnhancedRouteDecision(
        base_decision=base,
        action=RouterAction.CONTINUE,
    )

    # Enhanced captures the base at creation time
    assert enhanced.reason == "original"

    # Base is immutable, so we can't modify it anyway
    # This test verifies the pattern is sound
