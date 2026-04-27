"""
Tests for workflow logic fixes.

This module tests the fixes for:
1. retrieval_strategy parameter passing
2. hybrid route execution logic
3. router and adaptive planner conflict resolution
4. evidence sufficiency routing logic
5. query rewrite deduplication
6. parent-child score update
7. fast_path marker for casual chat
"""

import pytest
from unittest.mock import MagicMock, patch

from app.graph.workflow import (
    adaptive_planner_node,
    route_after_vector,
    route_after_graph,
    synthesis_node,
    GraphState,
)
from app.retrievers.hybrid_retriever import _collect_candidates
from app.services.adaptive_rag_policy import build_adaptive_plan


def test_retrieval_strategy_always_passed():
    """Test that retrieval_strategy is always passed to run_vector_rag."""
    from app.graph.workflow import vector_node

    state: GraphState = {
        "question": "test question",
        "route": "vector",
        "retrieval_strategy": "baseline",
        "allowed_sources": ["doc1.md"],
    }

    with patch("app.graph.workflow.run_vector_rag") as mock_rag:
        mock_rag.return_value = {"context": "", "citations": [], "retrieved_count": 0}
        vector_node(state)

        # Verify both parameters are passed
        mock_rag.assert_called_once()
        call_kwargs = mock_rag.call_args[1]
        assert "allowed_sources" in call_kwargs
        assert "retrieval_strategy" in call_kwargs
        assert call_kwargs["retrieval_strategy"] == "baseline"
        assert call_kwargs["allowed_sources"] == ["doc1.md"]


def test_hybrid_route_executes_both_in_parallel():
    """Test that hybrid route executes vector and graph in parallel without double execution."""
    from app.graph.workflow import vector_node, route_after_vector

    state: GraphState = {
        "question": "test question",
        "route": "hybrid",
        "adaptive_min_vector_hits": 2,
    }

    with patch("app.graph.workflow.submit_hybrid") as mock_submit:
        # Mock futures
        mock_vector_future = MagicMock()
        mock_graph_future = MagicMock()
        mock_vector_future.result.return_value = {"context": "vec", "citations": [], "retrieved_count": 2}
        mock_graph_future.result.return_value = {"context": "graph", "entities": [], "neighbors": []}

        mock_submit.side_effect = [mock_vector_future, mock_graph_future]

        result = vector_node(state)

        # Both should be executed in parallel
        assert mock_submit.call_count == 2
        assert "vector_result" in result
        assert "graph_result" in result

        # After vector_node with hybrid route, should go directly to synthesis if evidence sufficient
        next_route = route_after_vector(result)
        # Since both results exist, should check sufficiency and route accordingly
        assert next_route in ["synthesis", "web"]


def test_adaptive_planner_preserves_router_decision():
    """Test that adaptive planner only upgrades route complexity, never downgrades."""
    # Router decides vector, adaptive wants to upgrade to hybrid
    state: GraphState = {
        "question": "复杂的多步骤问题需要对比分析",
        "route": "vector",
        "reason": "router_decision",
        "skill": "answer_with_citations",
    }

    result = adaptive_planner_node(state)

    # Should upgrade to hybrid for complex query
    assert result["route"] == "hybrid"
    assert "adaptive_override" in result["reason"]

    # Router decides hybrid, adaptive wants vector (should preserve hybrid)
    state2: GraphState = {
        "question": "simple question",
        "route": "hybrid",
        "reason": "router_decision",
        "skill": "answer_with_citations",
    }

    result2 = adaptive_planner_node(state2)

    # Should preserve router's hybrid decision
    assert result2["route"] == "hybrid"


def test_route_after_vector_no_circular_dependency():
    """Test that route_after_vector correctly handles hybrid route without circular dependency."""
    # Hybrid route with both results present
    state: GraphState = {
        "question": "test",
        "route": "hybrid",
        "vector_result": {"context": "vec", "citations": [], "retrieved_count": 3, "effective_hit_count": 3},
        "graph_result": {"context": "graph", "entities": ["e1"], "neighbors": []},
        "adaptive_min_vector_hits": 2,
        "use_web_fallback": True,
    }

    next_route = route_after_vector(state)

    # Should go to synthesis (evidence sufficient) or web (insufficient)
    # Should NOT go to graph (already executed in parallel)
    assert next_route in ["synthesis", "web"]

    # Vector-only route should potentially go to graph if prefer_graph
    state2: GraphState = {
        "question": "test",
        "route": "vector",
        "vector_result": {"context": "vec", "citations": [], "retrieved_count": 1},
        "adaptive_min_vector_hits": 2,
        "adaptive_prefer_graph": True,
        "use_web_fallback": False,
    }

    next_route2 = route_after_vector(state2)
    assert next_route2 == "graph"


def test_route_after_graph_no_hybrid_check():
    """Test that route_after_graph doesn't check hybrid evidence when route is graph."""
    state: GraphState = {
        "question": "test",
        "route": "graph",
        "graph_result": {"context": "graph", "entities": ["e1", "e2"], "neighbors": []},
        "adaptive_min_vector_hits": 2,
        "use_web_fallback": True,
    }

    next_route = route_after_graph(state)

    # Should check graph-only evidence, not hybrid
    assert next_route in ["synthesis", "web"]


def test_query_rewrite_deduplication():
    """Test that query rewrites are deduplicated."""
    with patch("app.retrievers.hybrid_retriever.build_rewrite_queries") as mock_rewrite:
        # Return duplicates
        mock_rewrite.return_value = [
            "test query",
            "Test Query",  # Same after normalization
            "test query",  # Exact duplicate
            "different query",
        ]

        with patch("app.retrievers.hybrid_retriever._safe_similarity_search") as mock_search:
            mock_search.return_value = []
            with patch("app.retrievers.hybrid_retriever.bm25_search") as mock_bm25:
                mock_bm25.return_value = []

                candidates, diag = _collect_candidates(
                    query="test query",
                    allowed_sources=None,
                    vector_threshold=0.2,
                    retrieval_strategy="advanced",
                )

                # Should only have 2 unique variants
                assert len(diag["rewrites"]) == 2
                assert "test query" in diag["rewrites"]
                assert "different query" in diag["rewrites"]


def test_parent_child_score_update_preserves_all_scores():
    """Test that parent-child deduplication preserves all score fields."""
    from app.retrievers.hybrid_retriever import _expand_to_parent_context

    candidates = [
        {
            "id": "chunk1",
            "text": "child text 1",
            "metadata": {"parent_id": "parent1", "source": "doc.md"},
            "hybrid_score": 0.5,
            "dense_score": 0.4,
            "bm25_score": 0.1,
            "rerank_score": 0.6,
            "rank_feature_score": 0.05,
            "retrieval_sources": ["vector", "bm25"],
        },
        {
            "id": "chunk2",
            "text": "child text 2",
            "metadata": {"parent_id": "parent1", "source": "doc.md"},
            "hybrid_score": 0.8,  # Higher score
            "dense_score": 0.7,
            "bm25_score": 0.2,
            "rerank_score": 0.9,
            "rank_feature_score": 0.08,
            "retrieval_sources": ["vector"],
        },
    ]

    with patch("app.retrievers.hybrid_retriever.get_parent_text_map") as mock_parent:
        mock_parent.return_value = {"parent1": "parent text"}

        expanded = _expand_to_parent_context(candidates)

        # Should only have one result (deduplicated by parent_id)
        assert len(expanded) == 1

        # Should use the higher-scored item (chunk2)
        result = expanded[0]
        assert result["hybrid_score"] == 0.8
        assert result["dense_score"] == 0.7
        assert result["rerank_score"] == 0.9
        assert result["rank_feature_score"] == 0.08
        assert result["text"] == "parent text"
        assert result["child_text"] == "child text 2"


def test_casual_chat_fast_path_marker():
    """Test that casual chat adds fast_path marker to results."""
    state: GraphState = {
        "question": "你好",
    }

    result = synthesis_node(state)

    # Should have fast_path marker
    assert result["vector_result"].get("fast_path") is True
    assert result["graph_result"].get("fast_path") is True
    assert result["web_result"].get("fast_path") is True
    assert result["route"] == "smalltalk_fast"
    assert result["grounding"]["reason"] == "smalltalk_fast_path"


def test_adaptive_plan_respects_initial_route():
    """Test that adaptive plan respects router's initial decision."""
    # Simple query, router chose vector
    plan = build_adaptive_plan(
        question="simple question",
        initial_route="vector",
        skill="answer_with_citations",
        use_web_fallback=False,
        force_web=False,
    )

    assert plan.route == "vector"
    assert plan.level == "simple"

    # Complex query, router chose vector, should upgrade to hybrid
    plan2 = build_adaptive_plan(
        question="复杂的多步骤对比分析问题",
        initial_route="vector",
        skill="compare_entities",
        use_web_fallback=False,
        force_web=False,
    )

    assert plan2.route == "hybrid"
    assert plan2.level == "complex"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
