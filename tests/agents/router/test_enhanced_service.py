"""Unit tests for EnhancedRouterService with dynamic round limits."""

import pytest

from app.agents.router.enhanced_service import EnhancedRouterService
from app.domain.contracts import ClarificationContext, RouterAction
from app.orchestration.request import OrchestrationRequest, RequestScope


@pytest.mark.asyncio
async def test_dynamic_rounds_simple_query():
    """Simple query should set max_rounds=2."""
    service = EnhancedRouterService()
    request = OrchestrationRequest(
        question="价格是多少？",
        session_id="test_session",
        use_reasoning=False,
        source_scope=RequestScope(),
    )

    context = ClarificationContext()
    decision = await service.route(request, context)

    # Simple query should continue without clarification
    assert decision.action == RouterAction.CONTINUE
    assert decision.context.intent == "general_query"


@pytest.mark.asyncio
async def test_dynamic_rounds_rag_design():
    """RAG design query should set max_rounds=7."""
    service = EnhancedRouterService()
    request = OrchestrationRequest(
        question="帮我设计一个RAG系统",
        session_id="test_session",
        use_reasoning=False,
        source_scope=RequestScope(),
    )

    context = ClarificationContext()
    decision = await service.route(request, context)

    assert decision.context.intent == "rag_design"
    assert decision.context.max_rounds == 7


@pytest.mark.asyncio
async def test_dynamic_rounds_document_comparison():
    """Document comparison should set max_rounds=5."""
    service = EnhancedRouterService()
    request = OrchestrationRequest(
        question="比较两个方案的差异",
        session_id="test_session",
        use_reasoning=False,
        source_scope=RequestScope(),
    )

    context = ClarificationContext()
    decision = await service.route(request, context)

    assert decision.context.intent == "document_comparison"
    assert decision.context.max_rounds == 5


@pytest.mark.asyncio
async def test_intent_change_resets_max_rounds():
    """Intent change should reset max_rounds."""
    service = EnhancedRouterService()

    # First question: simple query
    request1 = OrchestrationRequest(
        question="价格？",
        session_id="test_session",
        use_reasoning=False,
        source_scope=RequestScope(),
    )
    context = ClarificationContext()
    decision1 = await service.route(request1, context)
    # Simple query continues immediately
    assert decision1.action == RouterAction.CONTINUE

    # Second question: RAG design (intent changed)
    request2 = OrchestrationRequest(
        question="设计一个RAG系统",
        session_id="test_session",
        use_reasoning=False,
        source_scope=RequestScope(),
    )
    context.clarification_round = 1  # Already asked 1 round
    decision2 = await service.route(request2, context)
    assert decision2.context.intent == "rag_design"
    assert decision2.context.max_rounds == 7  # Reset to new intent


@pytest.mark.asyncio
async def test_max_rounds_exceeded_forces_continue():
    """Exceeding max_rounds should force CONTINUE."""
    service = EnhancedRouterService()
    request = OrchestrationRequest(
        question="设计RAG",
        session_id="test_session",
        use_reasoning=False,
        source_scope=RequestScope(),
    )

    # Simulate already at max rounds
    context = ClarificationContext(
        intent="rag_design",
        max_rounds=7,
        clarification_round=7,  # Already at max
    )
    decision = await service.route(request, context)

    # Should force CONTINUE despite missing info
    assert decision.action == RouterAction.CONTINUE


@pytest.mark.asyncio
async def test_clarification_flow_with_missing_info():
    """Should return NEED_CLARIFICATION when info is missing."""
    service = EnhancedRouterService()
    request = OrchestrationRequest(
        question="设计RAG系统",  # Short question, missing details
        session_id="test_session",
        use_reasoning=False,
        source_scope=RequestScope(),
    )

    context = ClarificationContext()
    decision = await service.route(request, context)

    assert decision.context.intent == "rag_design"
    assert decision.action == RouterAction.NEED_CLARIFICATION
    assert decision.clarification is not None
    assert len(decision.missing_information) > 0


@pytest.mark.asyncio
async def test_extract_info_from_history():
    """Should extract known info from history."""
    service = EnhancedRouterService()
    from app.orchestration.request import ConversationTurn

    request = OrchestrationRequest(
        question="设计RAG系统",
        session_id="test_session",
        conversation=(
            ConversationTurn(role="user", content="我们需要一个企业知识库"),
            ConversationTurn(role="assistant", content="好的，数据来源是什么？"),
            ConversationTurn(role="user", content="数据来源是PDF文档"),
        ),
        use_reasoning=False,
        source_scope=RequestScope(),
    )

    context = ClarificationContext()
    decision = await service.route(request, context)

    # Should extract scenario and data_source from context
    assert decision.context.intent == "rag_design"
    # Should still need clarification for other fields
    assert decision.action == RouterAction.NEED_CLARIFICATION


@pytest.mark.asyncio
async def test_simple_query_skips_clarification():
    """Simple queries should skip clarification entirely."""
    service = EnhancedRouterService()

    # General query
    request1 = OrchestrationRequest(
        question="什么是RAG？",
        session_id="test_session",
        use_reasoning=False,
        source_scope=RequestScope(),
    )
    decision1 = await service.route(request1)
    assert decision1.action == RouterAction.CONTINUE

    # Long detailed question
    request2 = OrchestrationRequest(
        question="请帮我设计一个用于企业知识库的RAG系统，数据来源是PDF文档，规模约10GB，需要3秒内响应",
        session_id="test_session",
        use_reasoning=False,
        source_scope=RequestScope(),
    )
    decision2 = await service.route(request2)
    assert decision2.action == RouterAction.CONTINUE


@pytest.mark.asyncio
async def test_collected_info_reduces_clarification():
    """Collected info should reduce missing fields."""
    service = EnhancedRouterService()
    request = OrchestrationRequest(
        question="设计RAG系统",
        session_id="test_session",
        use_reasoning=False,
        source_scope=RequestScope(),
    )

    # First round: all fields missing
    context = ClarificationContext()
    decision1 = await service.route(request, context)
    assert decision1.action == RouterAction.NEED_CLARIFICATION
    initial_missing = len(decision1.missing_information)

    # Second round: one field collected
    context.collected_info = {"scenario": "企业知识库"}
    context.clarification_round = 1
    context.intent = "rag_design"
    context.max_rounds = 7
    decision2 = await service.route(request, context)
    assert decision2.action == RouterAction.NEED_CLARIFICATION
    assert len(decision2.missing_information) < initial_missing


@pytest.mark.asyncio
async def test_get_max_rounds_for_intent():
    """Test _get_max_rounds_for_intent helper."""
    service = EnhancedRouterService()

    assert service._get_max_rounds_for_intent("rag_design") == 7
    assert service._get_max_rounds_for_intent("document_comparison") == 5
    assert service._get_max_rounds_for_intent("specific_query") == 3
    assert service._get_max_rounds_for_intent("unknown_intent") == 5  # default


@pytest.mark.asyncio
async def test_select_next_question_priority():
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


@pytest.mark.asyncio
async def test_identify_intent():
    """Test intent identification logic."""
    service = EnhancedRouterService()

    # RAG design
    intent1 = await service._identify_intent("帮我设计一个RAG检索系统", {})
    assert intent1 == "rag_design"

    # Document comparison
    intent2 = await service._identify_intent("比较两个产品的差异", {})
    assert intent2 == "document_comparison"

    # Specific query
    intent3 = await service._identify_intent("这个产品的价格是多少？", {})
    assert intent3 == "specific_query"

    # General query
    intent4 = await service._identify_intent("请解释一下什么是RAG", {})
    assert intent4 == "general_query"


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
