"""
Tests for ReAct agent implementation.
"""

from unittest.mock import Mock, patch

import pytest

from app.agents.tool.react import (
    ReActAgent,
    run_react_agent,
)


class TestReActAgent:
    """Test suite for ReAct agent."""

    def test_react_agent_initialization(self):
        """Test ReAct agent can be initialized."""
        agent = ReActAgent(max_iterations=3, use_reasoning=False)
        assert agent.max_iterations == 3
        assert agent.use_reasoning is False
        assert len(agent.history) == 0
        assert "vector" in agent.accumulated_context
        assert "graph" in agent.accumulated_context
        assert "web" in agent.accumulated_context

    @patch("app.agents.tool.react.run_vector_rag")
    @patch("app.agents.tool.react.synthesize_answer")
    @patch("app.agents.tool.react.get_chat_model")
    def test_react_simple_query(
        self,
        mock_get_model,
        mock_synthesize,
        mock_vector,
    ):
        """Test ReAct handles simple query with vector search."""
        # Mock LLM responses
        mock_model = Mock()
        mock_get_model.return_value = mock_model

        # First call: decide to use vector_search
        thought_response = Mock()
        thought_response.content = """
        {
            "thought": "需要搜索本地文档",
            "action": "vector_search",
            "action_input": "APT28",
            "reasoning": "本地文档应该有相关信息"
        }
        """

        # Second call: decide to finish
        finish_response = Mock()
        finish_response.content = """
        {
            "thought": "信息足够了",
            "action": "finish",
            "action_input": "",
            "reasoning": "已经找到足够信息"
        }
        """

        mock_model.invoke.side_effect = [thought_response, finish_response]

        # Mock vector search
        mock_vector.return_value = {
            "context": "APT28是一个俄罗斯黑客组织",
            "citations": [{"source": "apt_report.pdf", "content": "..."}],
            "retrieved_count": 5,
            "effective_hit_count": 3,
        }

        # Mock synthesis
        mock_synthesize.return_value = {
            "answer": "APT28是一个俄罗斯黑客组织",
            "detected_language": "zh",
        }

        # Run agent
        agent = ReActAgent(max_iterations=5)
        result = agent.run("什么是APT28？")

        # Verify
        assert "answer" in result
        assert result["iterations_used"] == 2
        assert len(result["react_history"]) == 2
        assert mock_vector.called
        assert mock_synthesize.called

    @patch("app.agents.tool.react.run_vector_rag")
    @patch("app.agents.tool.react.synthesize_answer")
    @patch("app.agents.tool.react.get_chat_model")
    def test_react_resets_accumulated_context_between_runs(
        self,
        mock_get_model,
        mock_synthesize,
        mock_vector,
    ):
        """Test that each run starts with a fresh accumulated context."""
        mock_model = Mock()
        mock_get_model.return_value = mock_model

        mock_model.invoke.side_effect = [
            Mock(content='{"thought":"??","action":"vector_search","action_input":"first","reasoning":"????"}'),
            Mock(content='{"thought":"??","action":"finish","action_input":"","reasoning":"???"}'),
            Mock(content='{"thought":"????","action":"finish","action_input":"","reasoning":"????"}'),
        ]

        mock_vector.return_value = {
            "context": "first run context",
            "citations": [],
            "retrieved_count": 1,
            "effective_hit_count": 1,
        }

        captured_vector_contexts = []

        def capture_synthesis(**kwargs):
            captured_vector_contexts.append(kwargs.get("vector_context", ""))
            return {"answer": "ok", "detected_language": "zh"}

        mock_synthesize.side_effect = capture_synthesis

        agent = ReActAgent(max_iterations=3)
        first = agent.run("?????")
        second = agent.run("?????")

        assert "first run context" in captured_vector_contexts[0]
        assert captured_vector_contexts[1] == ""
        assert first["contexts"]["vector"].strip() == "first run context"
        assert second["contexts"]["vector"] == ""

    @patch("app.agents.tool.react.run_vector_rag")
    @patch("app.agents.tool.react.run_graph_rag")
    @patch("app.agents.tool.react.synthesize_answer")
    @patch("app.agents.tool.react.get_chat_model")
    def test_react_multi_tool_query(
        self,
        mock_get_model,
        mock_synthesize,
        mock_graph,
        mock_vector,
    ):
        """Test ReAct uses multiple tools."""
        # Mock LLM responses
        mock_model = Mock()
        mock_get_model.return_value = mock_model

        # Three thoughts: vector -> graph -> finish
        responses = [
            Mock(
                content='{"thought":"搜索向量","action":"vector_search","action_input":"test","reasoning":"需要文档"}'
            ),
            Mock(content='{"thought":"查询图谱","action":"graph_query","action_input":"test","reasoning":"需要关系"}'),
            Mock(content='{"thought":"完成","action":"finish","action_input":"","reasoning":"信息足够"}'),
        ]
        mock_model.invoke.side_effect = responses

        # Mock tools
        mock_vector.return_value = {
            "context": "vector context",
            "citations": [{"source": "doc.pdf", "content": "..."}],
            "retrieved_count": 3,
            "effective_hit_count": 2,
        }

        mock_graph.return_value = {
            "context": "graph context",
            "entities": ["Entity1"],
            "relationships": [],
        }

        mock_synthesize.return_value = {
            "answer": "Final answer",
            "detected_language": "zh",
        }

        # Run agent
        agent = ReActAgent(max_iterations=5)
        result = agent.run("复杂查询")

        # Verify both tools were called
        assert mock_vector.called
        assert mock_graph.called
        assert result["iterations_used"] == 3

    @patch("app.agents.tool.react.run_graph_rag")
    def test_react_graph_tool_passes_allowed_sources(self, mock_graph):
        """Test that graph tool reuses the same source scope as the workflow."""
        mock_graph.return_value = {
            "context": "graph context",
            "entities": [],
            "relationships": [],
        }

        agent = ReActAgent()
        agent._tool_graph_query("test", ["allowed.md"], None)

        mock_graph.assert_called_once_with("test", allowed_sources=["allowed.md"])

    @patch("app.agents.tool.react.run_graph_rag")
    def test_react_graph_summary_uses_neighbors_and_paths_when_relationships_missing(self, mock_graph):
        """Test that graph observations count neighbor/path evidence from the graph agent output."""
        mock_graph.return_value = {
            "context": "graph context",
            "entities": ["APT28"],
            "neighbors": [{"entity": "APT28", "relation": "uses", "other": "X-Agent"}],
            "paths": [{"source": "APT28", "middle": "X-Agent", "target": "Spearphishing"}],
        }

        agent = ReActAgent()
        summary, metadata = agent._tool_graph_query("test", ["allowed.md"], None)

        assert "APT28" in summary
        assert metadata["entities_count"] == 1
        assert metadata["relationships_count"] == 2
        assert len(agent.tool_results["graph"]["neighbors"]) == 1
        assert len(agent.tool_results["graph"]["paths"]) == 1

    @patch("app.agents.tool.react.run_vector_rag")
    def test_react_accumulates_vector_results_across_multiple_tool_calls(self, mock_vector):
        """Test that repeated vector searches keep earlier evidence instead of overwriting it."""
        mock_vector.side_effect = [
            {
                "context": "first context",
                "citations": [{"source": "first.md", "content": "a"}],
                "retrieved_count": 1,
                "effective_hit_count": 1,
            },
            {
                "context": "second context",
                "citations": [{"source": "second.md", "content": "b"}],
                "retrieved_count": 2,
                "effective_hit_count": 1,
            },
        ]

        agent = ReActAgent()
        agent._tool_vector_search("first", None, None)
        agent._tool_vector_search("second", None, None)

        vector_result = agent.tool_results["vector"]
        assert vector_result["retrieved_count"] == 3
        assert vector_result["effective_hit_count"] == 2
        assert len(vector_result["citations"]) == 2
        assert "first context" in vector_result["context"]
        assert "second context" in vector_result["context"]
        assert agent.accumulated_context["vector"] == vector_result["context"]

    def test_react_max_iterations(self):
        """Test ReAct respects max iterations limit."""
        agent = ReActAgent(max_iterations=2)

        with patch("app.agents.tool.react.get_chat_model") as mock_get_model:
            mock_model = Mock()
            mock_get_model.return_value = mock_model

            # Always return vector_search action (never finish)
            mock_model.invoke.return_value = Mock(
                content='{"thought":"继续","action":"vector_search","action_input":"test","reasoning":"继续搜索"}'
            )

            with patch("app.agents.tool.react.run_vector_rag") as mock_vector:
                mock_vector.return_value = {
                    "context": "",
                    "citations": [],
                    "retrieved_count": 0,
                    "effective_hit_count": 0,
                }

                with patch("app.agents.tool.react.synthesize_answer") as mock_synthesize:
                    mock_synthesize.return_value = {
                        "answer": "Timeout answer",
                        "detected_language": "zh",
                    }

                    result = agent.run("测试")

                    # Should stop after max_iterations
                    assert result["iterations_used"] <= 2

    def test_react_thought_extraction(self):
        """Test JSON extraction from LLM responses."""
        agent = ReActAgent()

        # Test valid JSON
        text = """
        Some preamble text
        ```json
        {"thought": "test", "action": "vector_search", "action_input": "query", "reasoning": "because"}
        ```
        """
        result = agent._extract_json(text)
        assert result["thought"] == "test"
        assert result["action"] == "vector_search"

        # Test JSON without code block
        text = '{"thought": "test2", "action": "finish", "action_input": "", "reasoning": "done"}'
        result = agent._extract_json(text)
        assert result["thought"] == "test2"

        # Test invalid JSON
        text = "No JSON here"
        result = agent._extract_json(text)
        assert result == {}

    def test_run_react_agent_convenience_function(self):
        """Test convenience function wrapper."""
        with patch("app.agents.tool.react.ReActAgent") as mock_class:
            mock_instance = Mock()
            mock_class.return_value = mock_instance
            mock_instance.run.return_value = {"answer": "test"}

            result = run_react_agent(
                question="test question",
                max_iterations=3,
                use_reasoning=True,
            )

            assert result == {"answer": "test"}
            mock_class.assert_called_once_with(
                max_iterations=3,
                use_reasoning=True,
            )
            mock_instance.run.assert_called_once()


class TestReActIntegration:
    """Integration tests for ReAct agent."""

    @pytest.mark.integration
    def test_react_agent_real_llm(self):
        """Test ReAct with real LLM (requires model backend)."""
        pytest.skip("Requires real LLM backend - run manually")

        agent = ReActAgent(max_iterations=3)
        result = agent.run(
            question="什么是APT28？",
            memory_context="",
        )

        assert "answer" in result
        assert "react_history" in result
        assert result["iterations_used"] > 0


@patch("app.agents.tool.react.run_vector_rag")
def test_react_vector_tool_passes_agent_class(mock_vector):
    mock_vector.return_value = {
        "context": "vector context",
        "citations": [],
        "retrieved_count": 1,
        "effective_hit_count": 1,
    }

    agent = ReActAgent()
    agent.agent_class = "cybersecurity"
    agent._tool_vector_search("test", ["allowed.md"], None)

    mock_vector.assert_called_once_with(
        question="test",
        allowed_sources=["allowed.md"],
        retrieval_strategy=None,
        agent_class="cybersecurity",
    )


@patch("app.agents.tool.react.run_graph_rag")
def test_react_graph_tool_passes_agent_class(mock_graph):
    mock_graph.return_value = {
        "context": "graph context",
        "entities": [],
        "neighbors": [],
        "paths": [],
    }

    agent = ReActAgent()
    agent.agent_class = "cybersecurity"
    agent._tool_graph_query("test", ["allowed.md"], None)

    mock_graph.assert_called_once_with(
        "test",
        allowed_sources=["allowed.md"],
        agent_class="cybersecurity",
    )
