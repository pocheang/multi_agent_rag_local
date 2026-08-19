"""Simple smoke test for EnhancedRouterService."""

import pytest

from app.agents.router.enhanced_service import EnhancedRouterService
from app.domain.contracts import ClarificationContext, RouterAction


def test_get_max_rounds_for_intent():
    """Test _get_max_rounds_for_intent helper."""
    service = EnhancedRouterService()

    assert service._get_max_rounds_for_intent("rag_design") == 7
    assert service._get_max_rounds_for_intent("document_comparison") == 5
    assert service._get_max_rounds_for_intent("specific_query") == 3
    assert service._get_max_rounds_for_intent("unknown_intent") == 5  # default


def test_is_simple_query():
    """Test simple query detection."""
    service = EnhancedRouterService()

    # General query is simple
    assert service._is_simple_query("什么是RAG？", "general_query") is True

    # Long question is simple
    long_q = "请帮我详细解释一下RAG系统的设计原理，包括向量检索、BM25和重排序的具体实现方式"
    assert service._is_simple_query(long_q, "rag_design") is True

    # Question with numbers is simple
    assert service._is_simple_query("产品A的价格是100元吗？", "specific_query") is True

    # Short RAG design question is not simple
    assert service._is_simple_query("设计RAG", "rag_design") is False


def test_check_missing_info():
    """Test missing information checking."""
    service = EnhancedRouterService()

    # All fields missing
    known1 = {}
    missing1 = service._check_missing_info("rag_design", known1)
    assert len(missing1) == 4  # scenario, data_source, scale, performance_requirement

    # Some fields present
    known2 = {"scenario": "企业知识库", "data_source": "PDF文档"}
    missing2 = service._check_missing_info("rag_design", known2)
    assert len(missing2) == 2  # scale, performance_requirement
    assert "scenario" not in missing2
    assert "data_source" not in missing2

    # All fields present
    known3 = {
        "scenario": "企业知识库",
        "data_source": "PDF文档",
        "scale": "中型",
        "performance_requirement": "快速",
    }
    missing3 = service._check_missing_info("rag_design", known3)
    assert len(missing3) == 0

    # Unknown intent
    missing4 = service._check_missing_info("unknown_intent", {})
    assert len(missing4) == 0


def test_extract_info_from_history_patterns():
    """Test pattern matching in _extract_info_from_history."""
    service = EnhancedRouterService()

    # Scenario extraction
    extracted1 = service._extract_info_from_history("企业内部知识管理", "")
    assert extracted1.get("scenario") == "企业知识库"

    extracted2 = service._extract_info_from_history("客服问答系统", "")
    assert extracted2.get("scenario") == "客服问答"

    # Data source extraction
    extracted3 = service._extract_info_from_history("处理PDF文档", "")
    assert extracted3.get("data_source") == "PDF文档"

    extracted4 = service._extract_info_from_history("从数据库读取", "")
    assert extracted4.get("data_source") == "数据库"

    # Scale extraction
    extracted5 = service._extract_info_from_history("小型系统，不到1GB", "")
    assert extracted5.get("scale") == "小型（<1GB）"

    extracted6 = service._extract_info_from_history("中等规模，大约5GB", "")
    assert extracted6.get("scale") == "中型（1-10GB）"


def test_select_next_question_priority():
    """Should select questions in field order."""
    service = EnhancedRouterService()

    missing = ["scenario", "data_source", "scale"]
    asked = []

    # First call: should return scenario
    q1 = service._select_next_question("rag_design", missing, asked)
    assert q1 is not None
    assert q1.field_name == "scenario"

    # Second call: scenario already asked
    asked = ["scenario"]
    q2 = service._select_next_question("rag_design", missing, asked)
    assert q2 is not None
    assert q2.field_name == "data_source"

    # Third call: scenario and data_source asked
    asked = ["scenario", "data_source"]
    q3 = service._select_next_question("rag_design", missing, asked)
    assert q3 is not None
    assert q3.field_name == "scale"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
