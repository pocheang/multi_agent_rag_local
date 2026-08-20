"""Manual accuracy tests for router with sample queries."""
import pytest
from app.agents.router.routing import decide_route


@pytest.mark.parametrize("query,expected_route", [
    ("What is deep learning?", "vector"),
    ("Who reports to the CEO?", "graph"),
    ("Compare Python and Java", "hybrid"),
    ("Find experts and recommend a team lead", "react"),
])
def test_routing_accuracy_samples(query, expected_route):
    """Test routing accuracy on sample queries."""
    decision = decide_route(query)
    assert decision.route == expected_route, f"Query: {query}, Got: {decision.route}, Expected: {expected_route}, Reason: {decision.reason}"
