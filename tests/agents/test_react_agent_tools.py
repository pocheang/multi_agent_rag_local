"""
ReactAgent工具使用单元测试

测试ReactAgent如何使用三个工具:
1. vector_search - 向量检索
2. graph_query - 图谱查询
3. web_search - 网络搜索

运行测试:
    pytest tests/agents/test_react_agent_tools.py -v
    pytest tests/agents/test_react_agent_tools.py -v -s  # 显示print输出
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from app.agents.tool.react import ReactAgent, ReActThought, ReActObservation


class TestReactAgentTools:
    """测试ReactAgent的工具使用机制"""

    @pytest.fixture
    def react_agent(self):
        """创建ReactAgent实例"""
        return ReactAgent(max_iterations=5, use_reasoning=False)

    @pytest.fixture
    def mock_vector_result(self):
        """Mock向量检索结果"""
        return {
            "context": "[doc1:p3] Transformer uses self-attention mechanism",
            "citations": [
                {
                    "source": "attention_paper.pdf",
                    "content": "Self-attention mechanism...",
                    "metadata": {"page": 3}
                }
            ],
            "retrieved_count": 15,
            "effective_hit_count": 12,
        }

    @pytest.fixture
    def mock_graph_result(self):
        """Mock图谱查询结果"""
        return {
            "context": "Transformer (type: Model) -[USES]-> Self-Attention (type: Mechanism)",
            "entities": ["Transformer", "Self-Attention"],
            "neighbors": [
                {"source": "Transformer", "relation": "USES", "target": "Self-Attention"}
            ],
            "paths": [],
            "graph_signal_score": 0.85,
        }

    @pytest.fixture
    def mock_web_result(self):
        """Mock网络搜索结果"""
        return {
            "context": "According to Wikipedia, Transformer is a deep learning model...",
            "citations": [
                {"source": "https://en.wikipedia.org/wiki/Transformer", "content": "..."}
            ],
            "used": True,
        }

    def test_tool_vector_search(self, react_agent, mock_vector_result):
        """测试vector_search工具"""
        with patch('app.agents.tool.react.run_vector_rag', return_value=mock_vector_result):
            summary, metadata = react_agent._tool_vector_search(
                query="What is Transformer?",
                allowed_sources=None,
                retrieval_strategy="hybrid"
            )

            # 验证摘要格式
            assert "Found 15 vector hits" in summary
            assert "12 effective hits" in summary
            assert "attention_paper.pdf" in summary

            # 验证元数据
            assert metadata["retrieved_count"] == 15
            assert metadata["effective_count"] == 12
            assert metadata["citations_count"] == 1

            # 验证结果已合并到accumulated_context
            assert "Transformer uses self-attention" in react_agent.accumulated_context["vector"]
            assert react_agent.tool_results["vector"]["retrieved_count"] == 15
            assert len(react_agent.tool_results["vector"]["citations"]) == 1

    def test_tool_graph_query(self, react_agent, mock_graph_result):
        """测试graph_query工具"""
        with patch('app.agents.tool.react.run_graph_rag', return_value=mock_graph_result):
            summary, metadata = react_agent._tool_graph_query(
                query="What is Transformer?",
                allowed_sources=None,
                retrieval_strategy=None
            )

            # 验证摘要格式
            assert "Found 2 entities" in summary
            assert "1 graph relationships" in summary
            assert "Transformer" in summary
            assert "Self-Attention" in summary

            # 验证元数据
            assert metadata["entities_count"] == 2
            assert metadata["relationships_count"] == 1

            # 验证结果已合并到accumulated_context
            assert "Transformer" in react_agent.accumulated_context["graph"]
            assert len(react_agent.tool_results["graph"]["entities"]) == 2
            assert react_agent.tool_results["graph"]["graph_signal_score"] == 0.85

    def test_tool_web_search(self, react_agent, mock_web_result):
        """测试web_search工具"""
        with patch('app.agents.tool.react.run_web_research', return_value=mock_web_result):
            summary, metadata = react_agent._tool_web_search(
                query="What is Transformer?",
                allowed_sources=None,
                retrieval_strategy=None
            )

            # 验证摘要格式
            assert "Found 1 web results" in summary
            assert "wikipedia.org" in summary

            # 验证元数据
            assert metadata["citations_count"] == 1
            assert metadata["used"] is True

            # 验证结果已合并到accumulated_context
            assert "Wikipedia" in react_agent.accumulated_context["web"]
            assert react_agent.tool_results["web"]["used"] is True

    def test_multiple_tool_calls_accumulation(self, react_agent, mock_vector_result):
        """测试多次工具调用的结果累积"""
        # 第一次调用
        with patch('app.agents.tool.react.run_vector_rag', return_value=mock_vector_result):
            react_agent._tool_vector_search("Query 1", None, None)

        assert react_agent.tool_results["vector"]["retrieved_count"] == 15

        # 第二次调用（结果应累加）
        mock_vector_result2 = {
            **mock_vector_result,
            "context": "[doc2:p5] RNN processes sequences sequentially",
            "retrieved_count": 10,
            "effective_hit_count": 8,
        }

        with patch('app.agents.tool.react.run_vector_rag', return_value=mock_vector_result2):
            react_agent._tool_vector_search("Query 2", None, None)

        # 验证累积效果
        assert react_agent.tool_results["vector"]["retrieved_count"] == 25  # 15 + 10
        assert react_agent.tool_results["vector"]["effective_hit_count"] == 20  # 12 + 8
        assert len(react_agent.tool_results["vector"]["citations"]) == 2
        assert "Transformer" in react_agent.accumulated_context["vector"]
        assert "RNN" in react_agent.accumulated_context["vector"]

    def test_context_append_logic(self, react_agent):
        """测试上下文追加逻辑"""
        # 测试空+新内容
        result1 = react_agent._append_context("", "Content 1")
        assert result1 == "Content 1"

        # 测试已有内容+新内容
        result2 = react_agent._append_context("Content 1", "Content 2")
        assert result2 == "Content 1\n\nContent 2"

        # 测试已有内容+空
        result3 = react_agent._append_context("Content 1", "")
        assert result3 == "Content 1"

        # 测试空+空
        result4 = react_agent._append_context("", "")
        assert result4 == ""

    def test_merge_vector_result(self, react_agent):
        """测试向量结果合并逻辑"""
        result1 = {
            "context": "Context 1",
            "citations": [{"id": 1}],
            "retrieved_count": 10,
            "effective_hit_count": 8,
            "retrieval_diagnostics": {"strategy": "hybrid"}
        }

        react_agent._merge_vector_result(result1)

        assert react_agent.tool_results["vector"]["context"] == "Context 1"
        assert react_agent.tool_results["vector"]["retrieved_count"] == 10
        assert len(react_agent.tool_results["vector"]["citations"]) == 1

        # 第二次合并
        result2 = {
            "context": "Context 2",
            "citations": [{"id": 2}, {"id": 3}],
            "retrieved_count": 5,
            "effective_hit_count": 4,
        }

        react_agent._merge_vector_result(result2)

        assert "Context 1" in react_agent.tool_results["vector"]["context"]
        assert "Context 2" in react_agent.tool_results["vector"]["context"]
        assert react_agent.tool_results["vector"]["retrieved_count"] == 15  # 10 + 5
        assert len(react_agent.tool_results["vector"]["citations"]) == 3

    def test_merge_graph_result(self, react_agent):
        """测试图谱结果合并逻辑"""
        result1 = {
            "context": "Graph Context 1",
            "entities": ["Entity1"],
            "neighbors": [{"relation": "R1"}],
            "paths": [{"path": "P1"}],
            "graph_signal_score": 0.7,
        }

        react_agent._merge_graph_result(result1)

        assert react_agent.tool_results["graph"]["graph_signal_score"] == 0.7
        assert len(react_agent.tool_results["graph"]["entities"]) == 1

        # 第二次合并（信号分数应取最大值）
        result2 = {
            "context": "Graph Context 2",
            "entities": ["Entity2"],
            "neighbors": [],
            "paths": [],
            "graph_signal_score": 0.9,  # 更高的分数
        }

        react_agent._merge_graph_result(result2)

        assert react_agent.tool_results["graph"]["graph_signal_score"] == 0.9  # 取最大值
        assert len(react_agent.tool_results["graph"]["entities"]) == 2

    def test_act_with_unknown_tool(self, react_agent):
        """测试使用未知工具"""
        observation = react_agent._act(
            action="unknown_tool",
            action_input="test query",
            allowed_sources=None,
            retrieval_strategy=None
        )

        assert observation.tool == "unknown_tool"
        assert "Unknown tool" in observation.result
        assert observation.metadata["error"] == "unknown_tool"

    def test_act_with_tool_error(self, react_agent):
        """测试工具执行错误处理"""
        with patch('app.agents.tool.react.run_vector_rag', side_effect=Exception("API Error")):
            observation = react_agent._act(
                action="vector_search",
                action_input="test query",
                allowed_sources=None,
                retrieval_strategy=None
            )

            assert observation.tool == "vector_search"
            assert "Tool execution failed" in observation.result
            assert "API Error" in observation.result

    def test_format_history(self, react_agent):
        """测试执行历史格式化"""
        # 添加一些历史记录
        from app.agents.tool.react import ReActStep, ReActThought, ReActObservation

        step1 = ReActStep(
            iteration=1,
            thought=ReActThought(
                thought="Need to search for Transformer",
                action="vector_search",
                action_input="Transformer architecture",
                reasoning="Get basic information"
            ),
            observation=ReActObservation(
                tool="vector_search",
                result="Found 15 documents",
                metadata={}
            )
        )

        step2 = ReActStep(
            iteration=2,
            thought=ReActThought(
                thought="Information sufficient",
                action="finish",
                action_input="",
                reasoning="Can generate answer"
            ),
            observation=None
        )

        react_agent.history = [step1, step2]

        history_text = react_agent._format_history()

        # 验证格式
        assert "第1轮:" in history_text
        assert "第2轮:" in history_text
        assert "思考:" in history_text
        assert "行动:" in history_text
        assert "推理:" in history_text
        assert "观察:" in history_text
        assert "vector_search" in history_text
        assert "finish" in history_text

    def test_extract_json(self, react_agent):
        """测试JSON提取功能"""
        # 测试markdown代码块格式
        text1 = """
        Some text before
        ```json
        {"action": "vector_search", "thought": "test"}
        ```
        Some text after
        """
        result1 = react_agent._extract_json(text1)
        assert result1["action"] == "vector_search"

        # 测试纯JSON格式
        text2 = 'Here is the response: {"action": "finish", "reasoning": "done"}'
        result2 = react_agent._extract_json(text2)
        assert result2["action"] == "finish"

        # 测试无JSON的情况
        text3 = "No JSON here at all"
        result3 = react_agent._extract_json(text3)
        assert result3 == {}

    @pytest.mark.parametrize("tool_name,expected_method", [
        ("vector_search", "_tool_vector_search"),
        ("graph_query", "_tool_graph_query"),
        ("web_search", "_tool_web_search"),
    ])
    def test_tool_mapping(self, react_agent, tool_name, expected_method):
        """测试工具映射表"""
        # 验证工具名称映射到正确的方法
        assert hasattr(react_agent, expected_method)

    def test_entity_name_extraction(self, react_agent):
        """测试实体名称提取"""
        # 字典格式
        entity1 = {"name": "Transformer", "type": "Model"}
        assert react_agent._entity_name(entity1) == "Transformer"

        # 使用entity字段
        entity2 = {"entity": "BERT", "type": "Model"}
        assert react_agent._entity_name(entity2) == "BERT"

        # 字符串格式
        entity3 = "GPT-3"
        assert react_agent._entity_name(entity3) == "GPT-3"

        # None情况
        entity4 = None
        assert react_agent._entity_name(entity4) == "unknown"

        # 空字典
        entity5 = {}
        assert react_agent._entity_name(entity5) == "unknown"


class TestReactAgentToolIntegration:
    """集成测试：模拟完整的工具调用流程"""

    @pytest.fixture
    def mock_llm_responses(self):
        """Mock LLM响应序列"""
        return [
            # 第1轮：决定使用vector_search
            Mock(content='{"thought": "Need basic info", "action": "vector_search", '
                        '"action_input": "Transformer model", "reasoning": "Get definition"}'),
            # 第2轮：决定使用graph_query
            Mock(content='{"thought": "Need relationships", "action": "graph_query", '
                        '"action_input": "Transformer relationships", "reasoning": "Get connections"}'),
            # 第3轮：决定finish
            Mock(content='{"thought": "Info sufficient", "action": "finish", '
                        '"action_input": "", "reasoning": "Can answer now"}'),
        ]

    def test_full_react_cycle_with_two_tools(self, mock_llm_responses):
        """测试完整的ReAct循环：使用两个工具后finish"""
        agent = ReactAgent(max_iterations=5, use_reasoning=False)

        # Mock LLM调用
        with patch('app.agents.tool.react.get_chat_model') as mock_model_getter, \
             patch('app.agents.tool.react.run_vector_rag') as mock_vector, \
             patch('app.agents.tool.react.run_graph_rag') as mock_graph, \
             patch('app.agents.tool.react.synthesize_answer') as mock_synthesis:

            # 配置mock
            mock_model = Mock()
            mock_model.invoke.side_effect = mock_llm_responses
            mock_model_getter.return_value = mock_model

            mock_vector.return_value = {
                "context": "Transformer is a model...",
                "citations": [{"source": "doc1"}],
                "retrieved_count": 10,
                "effective_hit_count": 8,
            }

            mock_graph.return_value = {
                "context": "Transformer -[USES]-> Attention",
                "entities": ["Transformer"],
                "neighbors": [],
                "paths": [],
                "graph_signal_score": 0.8,
            }

            mock_synthesis.return_value = {
                "answer": "Final answer with context",
                "detected_language": "zh",
            }

            # 执行
            result = agent.run(
                question="What is Transformer?",
                memory_context="",
                allowed_sources=None,
                retrieval_strategy="hybrid",
            )

            # 验证执行结果
            assert result["iterations_used"] == 3
            assert len(result["react_history"]) == 3

            # 验证第1轮使用了vector_search
            assert result["react_history"][0]["thought"]["action"] == "vector_search"
            assert result["react_history"][0]["observation"]["tool"] == "vector_search"

            # 验证第2轮使用了graph_query
            assert result["react_history"][1]["thought"]["action"] == "graph_query"
            assert result["react_history"][1]["observation"]["tool"] == "graph_query"

            # 验证第3轮finish
            assert result["react_history"][2]["thought"]["action"] == "finish"
            assert result["react_history"][2]["observation"] is None

            # 验证累积的上下文
            assert "Transformer is a model" in result["contexts"]["vector"]
            assert "Attention" in result["contexts"]["graph"]

            # 验证工具结果统计
            assert result["vector_result"]["retrieved_count"] == 10
            assert result["graph_result"]["graph_signal_score"] == 0.8

            # 验证synthesis被调用
            mock_synthesis.assert_called_once()
            call_kwargs = mock_synthesis.call_args[1]
            assert call_kwargs["question"] == "What is Transformer?"
            assert call_kwargs["vector_context"] == result["contexts"]["vector"]
            assert call_kwargs["graph_context"] == result["contexts"]["graph"]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
