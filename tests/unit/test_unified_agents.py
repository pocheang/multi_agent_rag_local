"""
Unit tests for the unified agent infrastructure.

Tests:
- BaseAgent functionality
- UnifiedConfig validation
- ResultSchemas correctness
- SharedUtils utilities
"""

import pytest
from unittest.mock import Mock, patch
from app.agents.shared.base import BaseAgent, AgentError, AgentValidationError, AgentTimeoutError
from app.agents.shared.config import (
    UnifiedAgentConfig,
    get_agent_config,
    set_agent_config,
    reset_agent_config,
)
from app.agents.result_schemas import (
    AgentResult,
    VectorRAGResult,
    GraphRAGResult,
    RouterResult,
)
from app.agents.shared.utils import (
    ContextFormatter,
    ResultValidator,
    CacheKeyGenerator,
    TextProcessor,
)


class TestBaseAgent:
    """Test BaseAgent functionality."""

    def test_base_agent_initialization(self):
        """Test BaseAgent can be initialized with config."""
        config = {"timeout_seconds": 60}

        class TestAgent(BaseAgent):
            def execute(self, query: str, **kwargs):
                return {"result": "test"}

        agent = TestAgent(config)
        assert agent.config == config
        assert agent.timeout_seconds == 60

    def test_base_agent_run_success(self):
        """Test successful agent execution."""
        class TestAgent(BaseAgent):
            def execute(self, query: str, **kwargs):
                return {"result": f"processed: {query}"}

        agent = TestAgent()
        result = agent.run(query="test query")

        assert result["status"] == "success"
        assert result["agent_name"] == "TestAgent"
        assert "execution_time_ms" in result
        assert result["result"] == "processed: test query"

    def test_base_agent_run_error_handling(self):
        """Test agent error handling."""
        class ErrorAgent(BaseAgent):
            def execute(self, query: str, **kwargs):
                raise ValueError("Test error")

        agent = ErrorAgent()
        result = agent.run(query="test")

        assert result["status"] == "failed"
        assert "error" in result
        assert "Test error" in result["error"]

    def test_base_agent_input_validation(self):
        """Test input validation."""
        class TestAgent(BaseAgent):
            def execute(self, query: str, **kwargs):
                return {"result": "ok"}

        agent = TestAgent()

        # Empty query should fail
        result = agent.run(query="")
        assert result["status"] == "failed"
        assert "AgentValidationError" in result["error_type"]

    def test_base_agent_config_methods(self):
        """Test config getter/setter methods."""
        class TestAgent(BaseAgent):
            def execute(self, query: str, **kwargs):
                return {"result": "ok"}

        agent = TestAgent()

        # Test get with default
        value = agent.get_config_value("non_existent", default="default_value")
        assert value == "default_value"

        # Test set
        agent.set_config_value("test_key", "test_value")
        assert agent.get_config_value("test_key") == "test_value"


class TestUnifiedConfig:
    """Test UnifiedConfig functionality."""

    def test_config_initialization(self):
        """Test config can be initialized with defaults."""
        config = UnifiedAgentConfig()

        assert config.router.confidence_threshold == 0.5
        assert config.vector_rag.top_k == 10
        assert config.graph_rag.enabled is True
        assert config.timeout_seconds == 30

    def test_config_validation(self):
        """Test config validation."""
        # Valid config
        config = UnifiedAgentConfig(
            timeout_seconds=60,
            log_level="DEBUG"
        )
        assert config.timeout_seconds == 60
        assert config.log_level == "DEBUG"

        # Invalid log level should be normalized
        with pytest.raises(ValueError):
            UnifiedAgentConfig(log_level="INVALID")

    def test_config_retrieval_strategy_validation(self):
        """Test retrieval strategy validation."""
        # Valid strategy
        config = UnifiedAgentConfig(vector_rag={"retrieval_strategy": "hybrid"})
        assert config.vector_rag.retrieval_strategy == "hybrid"

        # Invalid strategy
        with pytest.raises(ValueError):
            UnifiedAgentConfig(vector_rag={"retrieval_strategy": "invalid_strategy"})

    def test_config_singleton(self):
        """Test config singleton pattern."""
        reset_agent_config()

        config1 = get_agent_config()
        config2 = get_agent_config()

        assert config1 is config2

        # Modify and verify it persists
        config1.timeout_seconds = 100
        assert get_agent_config().timeout_seconds == 100

    def test_config_reset(self):
        """Test config can be reset to defaults."""
        config = get_agent_config()
        config.timeout_seconds = 100

        reset_agent_config()

        new_config = get_agent_config()
        assert new_config.timeout_seconds == 30  # Default value


class TestResultSchemas:
    """Test ResultSchemas functionality."""

    def test_agent_result_creation(self):
        """Test AgentResult can be created."""
        result = AgentResult(
            status="success",
            agent_name="TestAgent",
            answer="Test answer",
            execution_time_ms=123.45
        )

        assert result.status == "success"
        assert result.agent_name == "TestAgent"
        assert result.answer == "Test answer"
        assert result.execution_time_ms == 123.45

    def test_vector_rag_result(self):
        """Test VectorRAGResult with specific fields."""
        result = VectorRAGResult(
            status="success",
            agent_name="VectorRAG",
            context="Test context",
            retrieved_count=10,
            effective_hit_count=7,
            retrieval_strategy="hybrid"
        )

        assert result.retrieved_count == 10
        assert result.effective_hit_count == 7
        assert result.retrieval_strategy == "hybrid"

    def test_graph_rag_result(self):
        """Test GraphRAGResult with graph-specific fields."""
        result = GraphRAGResult(
            status="success",
            agent_name="GraphRAG",
            entities=["entity1", "entity2"],
            neighbors=[{"entity": "e1", "relation": "rel", "other": "e2"}],
            graph_signal_score=0.85
        )

        assert len(result.entities) == 2
        assert result.graph_signal_score == 0.85
        assert result.fallback_used is False

    def test_router_result(self):
        """Test RouterResult with routing fields."""
        result = RouterResult(
            status="success",
            agent_name="Router",
            route="vector",
            reason="Simple query",
            skill="answer_with_citations",
            agent_class="general",
            confidence=0.85
        )

        assert result.route == "vector"
        assert result.confidence == 0.85
        assert result.skill == "answer_with_citations"


class TestSharedUtils:
    """Test SharedUtils functionality."""

    def test_context_formatter_vector(self):
        """Test vector context formatting."""
        results = [
            {
                "text": "Test content 1",
                "metadata": {"source": "doc1.pdf"},
                "retrieval_sources": ["vector"]
            },
            {
                "text": "Test content 2",
                "metadata": {"source": "doc2.pdf"},
                "retrieval_sources": ["bm25"]
            }
        ]

        context = ContextFormatter.format_vector_context(results)

        assert "doc1.pdf" in context
        assert "doc2.pdf" in context
        assert "Test content 1" in context
        assert "vector" in context

    def test_context_formatter_merge(self):
        """Test context merging."""
        ctx1 = "Context 1"
        ctx2 = "Context 2"
        ctx3 = "Context 3"

        merged = ContextFormatter.merge_contexts(ctx1, ctx2, ctx3)

        assert "Context 1" in merged
        assert "Context 2" in merged
        assert "Context 3" in merged

    def test_result_validator(self):
        """Test result validation."""
        # Valid vector result
        valid_result = {
            "context": "test",
            "citations": [],
            "retrieved_count": 0
        }
        assert ResultValidator.validate_vector_result(valid_result) is True

        # Invalid result (missing keys)
        invalid_result = {"context": "test"}
        assert ResultValidator.validate_vector_result(invalid_result) is False

    def test_cache_key_generator(self):
        """Test cache key generation."""
        key1 = CacheKeyGenerator.generate_key(
            query="test query",
            param1="value1"
        )
        key2 = CacheKeyGenerator.generate_key(
            query="test query",
            param1="value1"
        )
        key3 = CacheKeyGenerator.generate_key(
            query="different query",
            param1="value1"
        )

        # Same inputs should produce same key
        assert key1 == key2

        # Different inputs should produce different keys
        assert key1 != key3

    def test_text_processor_extract_json(self):
        """Test JSON extraction from text."""
        # Test with markdown code block
        text1 = '```json\n{"key": "value"}\n```'
        result1 = TextProcessor.extract_json(text1)
        assert result1 == {"key": "value"}

        # Test with direct JSON
        text2 = 'Some text {"key": "value"} more text'
        result2 = TextProcessor.extract_json(text2)
        assert result2 == {"key": "value"}

        # Test with no JSON
        text3 = "No JSON here"
        result3 = TextProcessor.extract_json(text3)
        assert result3 == {}

    def test_text_processor_normalize(self):
        """Test string normalization."""
        text = "  Multiple   spaces   and\n\nnewlines  "
        normalized = TextProcessor.normalize_string(text)

        assert normalized == "Multiple spaces and newlines"

        # Test lowercase option
        normalized_lower = TextProcessor.normalize_string(text, lowercase=True)
        assert normalized_lower == "multiple spaces and newlines"

    def test_text_processor_truncate(self):
        """Test text truncation."""
        text = "A" * 100
        truncated = TextProcessor.truncate_text(text, max_length=50)

        assert len(truncated) == 50
        assert truncated.endswith("...")


class TestUnifiedVectorRAGAgent:
    """Test UnifiedVectorRAGAgent functionality."""

    @patch('app.agents.rag.vector.hybrid_search_with_diagnostics')
    def test_agent_initialization(self, mock_search):
        """Test agent can be initialized."""
        from app.agents.rag.vector import UnifiedVectorRAGAgent

        agent = UnifiedVectorRAGAgent()
        assert agent is not None
        assert agent.vector_config is not None

    @patch('app.agents.rag.vector.hybrid_search_with_diagnostics')
    def test_agent_execute(self, mock_search):
        """Test agent execution."""
        from app.agents.rag.vector import UnifiedVectorRAGAgent

        # Mock retrieval results
        mock_search.return_value = (
            [{"text": "test", "metadata": {"source": "test.pdf"}}],
            {}
        )

        agent = UnifiedVectorRAGAgent()
        result = agent.run(query="test query")

        assert result["status"] == "success"
        assert "context" in result
        assert "citations" in result

    @patch('app.agents.rag.vector.hybrid_search_with_diagnostics')
    def test_backward_compatible_function(self, mock_search):
        """Test backward-compatible function interface."""
        from app.agents.rag.vector import run_vector_rag

        # Mock retrieval results
        mock_search.return_value = (
            [{"text": "test", "metadata": {"source": "test.pdf"}}],
            {}
        )

        result = run_vector_rag(
            question="test query",
            retrieval_strategy="hybrid"
        )

        assert "context" in result
        assert "citations" in result
        assert "retrieved_count" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
