"""
Tests for Route Validator Agent.
"""

import pytest
from app.agents.router.validator import validate_route_decision
from app.agents.router.routing import LegacyRouteDecision as RouteDecision


@pytest.mark.asyncio
async def test_route_validator_high_confidence_fast_pass():
    """High confidence routes should pass quickly without LLM"""
    query = "什么是机器学习？"
    route_decision = RouteDecision(
        route="vector",
        reason="concept_query",
        skill="answer_with_citations",
        agent_class="general",
        confidence=0.92
    )

    result = await validate_route_decision(query, route_decision)

    assert result.is_valid is True
    assert result.confidence >= 0.85
    assert result.validation_method == "rule_fast"
    assert result.execution_time_ms < 50
    assert result.suggested_alternative is None


@pytest.mark.asyncio
async def test_route_validator_low_confidence_triggers_llm():
    """Low confidence should trigger LLM validation"""
    query = "张三和李四有什么关系"
    route_decision = RouteDecision(
        route="vector",
        reason="uncertain",
        skill="answer_with_citations",
        agent_class="general",
        confidence=0.45
    )

    result = await validate_route_decision(query, route_decision)

    assert result.validation_method in ["llm", "rule_feature"]
    assert result.execution_time_ms < 600


@pytest.mark.asyncio
async def test_route_validator_rule_based_validation():
    """Medium confidence should use rule-based validation"""
    query = "如何配置防火墙规则？"
    route_decision = RouteDecision(
        route="vector",
        reason="security_query",
        skill="answer_with_citations",
        agent_class="cybersecurity",
        confidence=0.70
    )

    result = await validate_route_decision(query, route_decision)

    assert result.is_valid is True
    assert result.validation_method == "rule_feature"
    assert result.execution_time_ms < 100


@pytest.mark.asyncio
async def test_route_validator_detects_graph_mismatch():
    """Should detect when relation query routed to wrong route"""
    query = "张三和李四有什么关系？"
    route_decision = RouteDecision(
        route="vector",  # Wrong! Should be graph
        reason="default",
        skill="answer_with_citations",
        agent_class="general",
        confidence=0.65
    )

    result = await validate_route_decision(query, route_decision)

    # Should detect the mismatch through rule validation
    assert result.warnings or result.confidence < 0.7


@pytest.mark.asyncio
async def test_route_validator_detects_invalid_route():
    """Should detect invalid route"""
    query = "什么是机器学习？"
    route_decision = RouteDecision(
        route="invalid_route",
        reason="test",
        skill="answer_with_citations",
        agent_class="general",
        confidence=0.70
    )

    result = await validate_route_decision(query, route_decision)

    # Should detect invalid route
    assert result.confidence < 0.6 or len(result.warnings) > 0


@pytest.mark.asyncio
async def test_route_validator_detects_invalid_skill():
    """Should detect invalid skill"""
    query = "什么是机器学习？"
    route_decision = RouteDecision(
        route="vector",
        reason="test",
        skill="invalid_skill",
        agent_class="general",
        confidence=0.70
    )

    result = await validate_route_decision(query, route_decision)

    # Should detect invalid skill
    assert result.confidence < 0.6 or len(result.warnings) > 0


@pytest.mark.asyncio
async def test_route_validator_pdf_query_validation():
    """Should validate PDF queries correctly"""
    query = "从PDF文件中提取文本内容"
    route_decision = RouteDecision(
        route="vector",
        reason="pdf_query",
        skill="pdf_text_reader",
        agent_class="general",
        confidence=0.75
    )

    result = await validate_route_decision(query, route_decision)

    assert result.is_valid is True
    assert result.validation_method in ["rule_fast", "rule_feature"]


@pytest.mark.asyncio
async def test_route_validator_comparison_query():
    """Should validate comparison queries"""
    query = "对比GPT-4和Claude的区别"
    route_decision = RouteDecision(
        route="hybrid",
        reason="comparison_query",
        skill="compare_entities",
        agent_class="general",
        confidence=0.70
    )

    result = await validate_route_decision(query, route_decision)

    assert result.is_valid is True
    assert result.validation_method == "rule_feature"


@pytest.mark.asyncio
async def test_route_validator_no_cache():
    """Should work without cache"""
    query = "什么是机器学习？"
    route_decision = RouteDecision(
        route="vector",
        reason="concept_query",
        skill="answer_with_citations",
        agent_class="general",
        confidence=0.92
    )

    result = await validate_route_decision(query, route_decision, use_cache=False)

    assert result.is_valid is True
    assert result.confidence >= 0.85
