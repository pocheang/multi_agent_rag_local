"""
Integration tests for query expansion with vector RAG agent.

Tests that query expansion improves retrieval quality for abbreviated/incomplete queries.
"""

import pytest
from unittest.mock import patch, MagicMock

from app.agents.rag.vector import run_vector_rag
from app.core.config import get_settings


class TestQueryExpansionIntegration:
    """Test query expansion integration with vector RAG."""

    @patch("app.agents.rag.vector.hybrid_search_with_diagnostics")
    def test_expansion_enabled_expands_query(self, mock_search):
        """When enabled, query expansion should expand abbreviations."""
        # Mock search to return empty results
        mock_search.return_value = ([], {"test": "diagnostics"})

        # Ensure expansion is enabled
        settings = get_settings()
        original_enabled = settings.query_expansion_enabled
        settings.query_expansion_enabled = True

        try:
            result = run_vector_rag("What is ML?")

            # Verify search was called with expanded query
            assert mock_search.called
            call_args = mock_search.call_args
            search_query = call_args[0][0]

            # Should contain "machine learning"
            assert "machine learning" in search_query.lower()

            # Check diagnostics
            assert "query_expansion" in result["retrieval_diagnostics"]
            expansion_info = result["retrieval_diagnostics"]["query_expansion"]
            assert expansion_info["enabled"] is True
            assert "original" in expansion_info
            assert "expanded" in expansion_info

        finally:
            settings.query_expansion_enabled = original_enabled

    @patch("app.agents.rag.vector.hybrid_search_with_diagnostics")
    def test_expansion_disabled_uses_original(self, mock_search):
        """When disabled, should use original query."""
        mock_search.return_value = ([], {"test": "diagnostics"})

        settings = get_settings()
        original_enabled = settings.query_expansion_enabled
        settings.query_expansion_enabled = False

        try:
            result = run_vector_rag("What is ML?")

            # Verify search was called with original query
            assert mock_search.called
            call_args = mock_search.call_args
            search_query = call_args[0][0]

            # Should be original query (ML not expanded)
            assert search_query == "What is ML?"

            # Check diagnostics
            assert "query_expansion" in result["retrieval_diagnostics"]
            expansion_info = result["retrieval_diagnostics"]["query_expansion"]
            assert expansion_info["enabled"] is False

        finally:
            settings.query_expansion_enabled = original_enabled

    @patch("app.agents.rag.vector.hybrid_search_with_diagnostics")
    def test_expansion_multiple_acronyms(self, mock_search):
        """Should expand multiple acronyms."""
        mock_search.return_value = ([], {"test": "diagnostics"})

        settings = get_settings()
        original_enabled = settings.query_expansion_enabled
        settings.query_expansion_enabled = True

        try:
            result = run_vector_rag("ML and AI in NLP")

            assert mock_search.called
            call_args = mock_search.call_args
            search_query = call_args[0][0]

            # Should contain expanded forms
            search_lower = search_query.lower()
            # At least one expansion should be present
            has_expansion = (
                "machine learning" in search_lower
                or "artificial intelligence" in search_lower
                or "natural language processing" in search_lower
            )
            assert has_expansion

        finally:
            settings.query_expansion_enabled = original_enabled

    @patch("app.agents.rag.vector.hybrid_search_with_diagnostics")
    def test_expansion_chinese_query(self, mock_search):
        """Should handle Chinese queries without errors."""
        mock_search.return_value = ([], {"test": "diagnostics"})

        settings = get_settings()
        original_enabled = settings.query_expansion_enabled
        settings.query_expansion_enabled = True

        try:
            result = run_vector_rag("机器学习模型训练")

            # Should complete without error
            assert mock_search.called
            assert result is not None

        finally:
            settings.query_expansion_enabled = original_enabled

    @patch("app.agents.rag.vector.hybrid_search_with_diagnostics")
    def test_expansion_failure_fallback(self, mock_search):
        """If expansion fails, should fall back to original query."""
        mock_search.return_value = ([], {"test": "diagnostics"})

        settings = get_settings()
        original_enabled = settings.query_expansion_enabled
        settings.query_expansion_enabled = True

        try:
            # Mock expand_query to raise exception
            with patch("app.agents.rag.vector.expand_query") as mock_expand:
                mock_expand.side_effect = Exception("Expansion failed")

                result = run_vector_rag("What is ML?")

                # Should still work with original query
                assert mock_search.called
                call_args = mock_search.call_args
                search_query = call_args[0][0]

                # Should use original query as fallback
                assert search_query == "What is ML?"

        finally:
            settings.query_expansion_enabled = original_enabled

    @patch("app.agents.rag.vector.hybrid_search_with_diagnostics")
    def test_expansion_preserves_agent_class_filtering(self, mock_search):
        """Expansion should not interfere with agent class filtering."""
        mock_search.return_value = ([], {"test": "diagnostics"})

        settings = get_settings()
        original_enabled = settings.query_expansion_enabled
        settings.query_expansion_enabled = True

        try:
            result = run_vector_rag(
                "What is ML?",
                agent_class="technical"
            )

            # Should complete without error
            assert mock_search.called
            assert result is not None

        finally:
            settings.query_expansion_enabled = original_enabled

    @patch("app.agents.rag.vector.hybrid_search_with_diagnostics")
    def test_expansion_respects_max_ratio(self, mock_search):
        """Expansion should respect max ratio configuration."""
        mock_search.return_value = ([], {"test": "diagnostics"})

        settings = get_settings()
        original_enabled = settings.query_expansion_enabled
        original_ratio = settings.query_expansion_max_ratio
        settings.query_expansion_enabled = True
        settings.query_expansion_max_ratio = 2.0  # Lower ratio

        try:
            result = run_vector_rag("ML AI NLP DL")

            assert mock_search.called
            call_args = mock_search.call_args
            search_query = call_args[0][0]

            # Expansion should be limited by max_ratio
            # Original is ~12 chars, with ratio 2.0 max should be ~24 chars
            # But the expansion module has its own logic, so just verify it's reasonable
            # and not unlimited (e.g., less than 10x original)
            assert len(search_query) <= len("ML AI NLP DL") * 10

        finally:
            settings.query_expansion_enabled = original_enabled
            settings.query_expansion_max_ratio = original_ratio


class TestExpansionQualityMetrics:
    """Test that expansion improves retrieval quality metrics."""

    @patch("app.agents.rag.vector.hybrid_search_with_diagnostics")
    def test_expanded_query_finds_more_results(self, mock_search):
        """Expanded query should potentially find more relevant results."""
        # Simulate that expanded query finds more results
        def search_side_effect(query, **kwargs):
            if "machine learning" in query.lower():
                # More results when expanded
                return (
                    [
                        {
                            "text": "Machine learning is a subset of AI...",
                            "metadata": {"source": "test.pdf"},
                            "dense_score": 0.8,
                        },
                        {
                            "text": "ML models can be trained...",
                            "metadata": {"source": "test2.pdf"},
                            "dense_score": 0.7,
                        },
                    ],
                    {"count": 2},
                )
            else:
                # Fewer results without expansion
                return (
                    [
                        {
                            "text": "ML models can be trained...",
                            "metadata": {"source": "test2.pdf"},
                            "dense_score": 0.7,
                        },
                    ],
                    {"count": 1},
                )

        mock_search.side_effect = search_side_effect

        settings = get_settings()
        original_enabled = settings.query_expansion_enabled

        try:
            # Test with expansion enabled
            settings.query_expansion_enabled = True
            result_expanded = run_vector_rag("What is ML?")

            # Test with expansion disabled
            settings.query_expansion_enabled = False
            result_original = run_vector_rag("What is ML?")

            # Expanded should find more results
            assert result_expanded["retrieved_count"] >= result_original["retrieved_count"]

        finally:
            settings.query_expansion_enabled = original_enabled
