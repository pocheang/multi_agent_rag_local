"""
Tests for quality assurance data models.
"""

import pytest
from datetime import datetime
from app.agents.shared.quality_models import (
    RouteValidationResult,
    RetrievalQualityResult,
    RetrievalQualityMetrics,
    AnswerValidationResult,
    AnswerValidationDetails,
    AnswerIssue,
    QualityReport,
    QualityBreakdown,
    ExecutionStats,
    ConversationTurn,
    ConversationContext,
    ContextHints,
)


# ============================================================================
# RouteValidationResult Tests
# ============================================================================

def test_route_validation_result_creation():
    """Test basic RouteValidationResult creation with valid values."""
    result = RouteValidationResult(
        is_valid=True,
        confidence=0.92,
        validation_method="rule_fast",
        validation_reason="high_confidence_fast_pass",
        execution_time_ms=8,
        suggested_alternative=None,
        warnings=[]
    )
    assert result.is_valid is True
    assert result.confidence == 0.92
    assert result.validation_method == "rule_fast"
    assert 0.0 <= result.confidence <= 1.0


def test_route_validation_with_alternative():
    """Test RouteValidationResult with suggested alternative."""
    result = RouteValidationResult(
        is_valid=False,
        confidence=0.45,
        validation_method="llm",
        validation_reason="low_confidence_mismatch",
        execution_time_ms=320,
        suggested_alternative={"route": "graph", "skill": "compare_entities"},
        warnings=["route_mismatch"]
    )
    assert result.is_valid is False
    assert result.suggested_alternative is not None
    assert result.suggested_alternative["route"] == "graph"


def test_route_validation_confidence_bounds():
    """Test RouteValidationResult enforces confidence bounds."""
    with pytest.raises(ValueError):
        RouteValidationResult(
            is_valid=True,
            confidence=1.5,  # Invalid: > 1.0
            validation_method="rule_fast",
            validation_reason="test",
            execution_time_ms=10
        )

    with pytest.raises(ValueError):
        RouteValidationResult(
            is_valid=True,
            confidence=-0.1,  # Invalid: < 0.0
            validation_method="rule_fast",
            validation_reason="test",
            execution_time_ms=10
        )


def test_route_validation_method_validation():
    """Test RouteValidationResult validates method literals."""
    with pytest.raises(ValueError):
        RouteValidationResult(
            is_valid=True,
            confidence=0.5,
            validation_method="invalid_method",  # Invalid literal
            validation_reason="test",
            execution_time_ms=10
        )


# ============================================================================
# RetrievalQualityResult Tests
# ============================================================================

def test_retrieval_quality_metrics_creation():
    """Test RetrievalQualityMetrics creation with valid scores."""
    metrics = RetrievalQualityMetrics(
        coverage_score=0.85,
        relevance_score=0.92,
        diversity_score=0.70,
        completeness_score=0.88
    )
    assert metrics.coverage_score == 0.85
    assert metrics.relevance_score == 0.92
    assert metrics.diversity_score == 0.70
    assert metrics.completeness_score == 0.88


def test_retrieval_quality_metrics_bounds():
    """Test RetrievalQualityMetrics enforces score bounds."""
    with pytest.raises(ValueError):
        RetrievalQualityMetrics(
            coverage_score=1.5,  # Invalid: > 1.0
            relevance_score=0.8,
            diversity_score=0.7,
            completeness_score=0.8
        )


def test_retrieval_quality_result_creation():
    """Test RetrievalQualityResult creation with metrics."""
    metrics = RetrievalQualityMetrics(
        coverage_score=0.85,
        relevance_score=0.92,
        diversity_score=0.70,
        completeness_score=0.88
    )
    result = RetrievalQualityResult(
        overall_quality=0.84,
        metrics=metrics,
        execution_time_ms=150,
        issues=["low_diversity"],
        suggestions=["increase_source_variety"]
    )
    assert result.overall_quality == 0.84
    assert result.metrics.relevance_score == 0.92
    assert len(result.issues) == 1
    assert result.execution_time_ms == 150


# ============================================================================
# AnswerValidationResult Tests
# ============================================================================

def test_answer_validation_details_creation():
    """Test AnswerValidationDetails creation with all metrics."""
    details = AnswerValidationDetails(
        factual_consistency=0.95,
        hallucination_risk=0.05,
        citation_completeness=0.90,
        answer_quality=0.88,
        safety_score=0.99
    )
    assert details.factual_consistency == 0.95
    assert details.hallucination_risk == 0.05
    assert details.citation_completeness == 0.90
    assert details.answer_quality == 0.88
    assert details.safety_score == 0.99


def test_answer_issue_creation():
    """Test AnswerIssue creation with all fields."""
    issue = AnswerIssue(
        type="unsupported_claim",
        content="The model claimed X without evidence",
        severity="high",
        suggestion="Remove unsupported claim or add citation",
        location="paragraph 2"
    )
    assert issue.type == "unsupported_claim"
    assert issue.severity == "high"
    assert issue.location == "paragraph 2"


def test_answer_validation_result_creation():
    """Test AnswerValidationResult creation with full details."""
    details = AnswerValidationDetails(
        factual_consistency=0.95,
        hallucination_risk=0.05,
        citation_completeness=0.90,
        answer_quality=0.88,
        safety_score=0.99
    )
    issue = AnswerIssue(
        type="missing_citation",
        content="Claim needs citation",
        severity="medium",
        suggestion="Add citation for this claim",
        location="paragraph 1"
    )
    result = AnswerValidationResult(
        is_valid=True,
        overall_score=0.88,
        validation_details=details,
        issues=[issue],
        action="approve",
        execution_time_ms=500,
        validation_method="standard"
    )
    assert result.is_valid is True
    assert result.overall_score == 0.88
    assert result.action == "approve"
    assert len(result.issues) == 1


def test_answer_validation_action_validation():
    """Test AnswerValidationResult validates action literals."""
    details = AnswerValidationDetails(
        factual_consistency=0.95,
        hallucination_risk=0.05,
        citation_completeness=0.90,
        answer_quality=0.88,
        safety_score=0.99
    )
    with pytest.raises(ValueError):
        AnswerValidationResult(
            is_valid=True,
            overall_score=0.88,
            validation_details=details,
            issues=[],
            action="invalid_action",  # Invalid literal
            execution_time_ms=500,
            validation_method="standard"
        )


# ============================================================================
# QualityReport Tests
# ============================================================================

def test_quality_report_creation():
    """Test QualityReport creation with all components."""
    breakdown = QualityBreakdown(
        route_decision={"confidence": 0.92, "method": "rule_fast"},
        retrieval={"coverage": 0.85, "relevance": 0.92},
        answer_factuality={"score": 0.95, "issues": 0},
        citations={"completeness": 0.90, "count": 5}
    )
    exec_stats = ExecutionStats(
        total_time_ms=800,
        validation_overhead_ms=200,
        retry_count=0,
        route_retry=0,
        answer_retry=0
    )
    report = QualityReport(
        overall_confidence=0.90,
        quality_level="high",
        quality_label="Excellent Response",
        user_prompt="What is X?",
        breakdown=breakdown,
        issues=[],
        suggestions=["Consider more sources"],
        execution_stats=exec_stats
    )
    assert report.overall_confidence == 0.90
    assert report.quality_level == "high"
    assert report.quality_label == "Excellent Response"
    assert report.execution_stats.total_time_ms == 800


def test_quality_report_quality_level_validation():
    """Test QualityReport validates quality_level literals."""
    breakdown = QualityBreakdown(
        route_decision={},
        retrieval={},
        answer_factuality={},
        citations={}
    )
    exec_stats = ExecutionStats(
        total_time_ms=100,
        validation_overhead_ms=50,
        retry_count=0
    )
    with pytest.raises(ValueError):
        QualityReport(
            overall_confidence=0.90,
            quality_level="invalid_level",  # Invalid literal
            quality_label="Test",
            breakdown=breakdown,
            execution_stats=exec_stats
        )


# ============================================================================
# ConversationContext Tests
# ============================================================================

def test_conversation_turn_creation():
    """Test ConversationTurn creation with all fields."""
    now = datetime.utcnow()
    turn = ConversationTurn(
        query="What is machine learning?",
        response="Machine learning is...",
        route="vector",
        entities=["machine_learning", "ai"],
        timestamp=now
    )
    assert turn.query == "What is machine learning?"
    assert turn.route == "vector"
    assert len(turn.entities) == 2
    assert turn.timestamp == now


def test_conversation_context_creation():
    """Test ConversationContext creation."""
    now = datetime.utcnow()
    context = ConversationContext(
        session_id="sess_123",
        user_id="user_456",
        conversation_history=[],
        topic_stack=["machine_learning"],
        entity_mentions={"ai": 5},
        current_intent="definition_request",
        context_summary="User asking about ML",
        last_update_time=now
    )
    assert context.session_id == "sess_123"
    assert context.user_id == "user_456"
    assert len(context.topic_stack) == 1
    assert context.entity_mentions["ai"] == 5


def test_conversation_context_max_history():
    """Test ConversationContext enforces max history length."""
    now = datetime.utcnow()
    turns = [
        ConversationTurn(
            query=f"Query {i}",
            response=f"Response {i}",
            route="vector",
            timestamp=now
        )
        for i in range(12)  # More than max of 10
    ]
    with pytest.raises(ValueError):
        ConversationContext(
            session_id="sess_123",
            user_id="user_456",
            conversation_history=turns,
            last_update_time=now
        )


def test_context_hints_creation():
    """Test ContextHints creation with optional fields."""
    hints = ContextHints(
        resolve_references={"entity_1": 1, "entity_2": 2},
        followup=True,
        previous_route="graph",
        focus_entities=["entity_1", "entity_2"]
    )
    assert hints.followup is True
    assert hints.previous_route == "graph"
    assert len(hints.focus_entities) == 2


def test_context_hints_with_defaults():
    """Test ContextHints with default values."""
    hints = ContextHints()
    assert hints.resolve_references is None
    assert hints.followup is False
    assert hints.previous_route is None
    assert hints.focus_entities == []


# ============================================================================
# Execution Stats Tests
# ============================================================================

def test_execution_stats_creation():
    """Test ExecutionStats creation with all fields."""
    stats = ExecutionStats(
        total_time_ms=1000,
        validation_overhead_ms=300,
        retry_count=1,
        route_retry=1,
        answer_retry=0
    )
    assert stats.total_time_ms == 1000
    assert stats.validation_overhead_ms == 300
    assert stats.retry_count == 1
    assert stats.route_retry == 1
    assert stats.answer_retry == 0


def test_execution_stats_defaults():
    """Test ExecutionStats uses default values."""
    stats = ExecutionStats(
        total_time_ms=500,
        validation_overhead_ms=100,
        retry_count=0
    )
    assert stats.route_retry == 0
    assert stats.answer_retry == 0
