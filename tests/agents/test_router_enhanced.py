"""Tests for enhanced router agent with few-shot examples."""
import pytest
from app.agents.router.examples import (
    get_few_shot_examples_by_route,
    format_examples_for_prompt,
    EXAMPLE_VECTOR_QUERIES,
    EXAMPLE_GRAPH_QUERIES,
    EXAMPLE_HYBRID_QUERIES,
)


def test_few_shot_examples_structure():
    """Test that few-shot examples have required fields."""
    for route_type in ["vector", "graph", "hybrid", "react"]:
        examples = get_few_shot_examples_by_route(route_type)
        assert len(examples) >= 3, f"{route_type} should have at least 3 examples"

        for ex in examples:
            assert "query" in ex
            assert "route" in ex
            assert "reason" in ex
            assert "confidence" in ex
            assert isinstance(ex["confidence"], float)
            assert 0.0 <= ex["confidence"] <= 1.0


def test_format_examples_for_prompt():
    """Test that examples are formatted correctly for LLM prompt."""
    examples = get_few_shot_examples_by_route("vector", count=2)
    formatted = format_examples_for_prompt(examples)

    assert "Query:" in formatted
    assert "Route:" in formatted
    assert "Reason:" in formatted
    assert "Confidence:" in formatted
    assert len(formatted) > 100  # Should be substantial text


def test_example_vector_queries_content():
    """Test vector query examples are appropriate."""
    assert len(EXAMPLE_VECTOR_QUERIES) >= 5

    # Check for concept/definition queries
    concept_queries = [ex for ex in EXAMPLE_VECTOR_QUERIES if "definition" in ex["reason"].lower() or "concept" in ex["reason"].lower()]
    assert len(concept_queries) >= 2


def test_enhanced_router_prompt_includes_examples():
    """Test that enhanced prompt includes few-shot examples."""
    from app.agents.router.routing import ROUTER_PROMPT

    # Should include few-shot examples
    assert "Example" in ROUTER_PROMPT or "examples" in ROUTER_PROMPT.lower()

    # Should include reasoning instruction
    assert "reason" in ROUTER_PROMPT.lower() or "explain" in ROUTER_PROMPT.lower()

    # Should still have route options
    assert "vector" in ROUTER_PROMPT
    assert "graph" in ROUTER_PROMPT
    assert "hybrid" in ROUTER_PROMPT


def test_decide_route_returns_enhanced_decision():
    """Test that decide_route returns decision with reasoning."""
    from app.agents.router.routing import decide_route

    decision = decide_route("What is machine learning?")

    assert hasattr(decision, "route")
    assert hasattr(decision, "reason")
    assert hasattr(decision, "confidence")
    assert hasattr(decision, "skill")

    # Reason should be non-empty
    assert len(decision.reason) > 10
