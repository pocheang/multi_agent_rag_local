"""
Tests for Quality Orchestrator Agent.

Tests weighted scoring fusion, penalty rules, quality classification, and issue aggregation.
"""

import pytest
import time
from app.agents.quality_models import (
    RouteValidationResult,
    RetrievalQualityResult,
    RetrievalQualityMetrics,
    AnswerValidationResult,
    AnswerValidationDetails,
    AnswerIssue,
    QualityReport
)
from app.agents.validation.quality_orchestrator import orchestrate_quality, _classify_quality_level


class TestQualityLevelClassification:
    """Test quality level classification thresholds"""

    def test_high_quality_classification(self):
        """High quality: ≥0.85, no user prompt"""
        level, label, prompt = _classify_quality_level(0.90)
        assert level == "high"
        assert label == "高质量"
        assert prompt is None

        # Boundary test
        level, label, prompt = _classify_quality_level(0.85)
        assert level == "high"
        assert prompt is None

    def test_medium_quality_classification(self):
        """Medium quality: 0.70-0.85, suggests verification"""
        level, label, prompt = _classify_quality_level(0.75)
        assert level == "medium"
        assert label == "中等质量"
        assert "建议结合其他来源验证" in prompt

        # Boundary test
        level, label, prompt = _classify_quality_level(0.70)
        assert level == "medium"

    def test_low_quality_classification(self):
        """Low quality: 0.50-0.70, caution recommended"""
        level, label, prompt = _classify_quality_level(0.60)
        assert level == "low"
        assert label == "低质量"
        assert "请谨慎参考" in prompt
        assert "建议人工核实" in prompt

        # Boundary test
        level, label, prompt = _classify_quality_level(0.50)
        assert level == "low"

    def test_very_low_quality_classification(self):
        """Very low quality: <0.50, strong warning"""
        level, label, prompt = _classify_quality_level(0.40)
        assert level == "very_low"
        assert label == "极低质量"
        assert "⚠️" in prompt
        assert "强烈建议人工审核" in prompt


class TestWeightedScoring:
    """Test weighted scoring fusion from all validators"""

    def test_high_quality_fusion(self):
        """Test fusion of all high quality scores"""
        route_val = RouteValidationResult(
            is_valid=True,
            confidence=0.92,
            validation_method="rule_fast",
            validation_reason="high_confidence",
            execution_time_ms=10,
            warnings=[]
        )

        retrieval_qual = RetrievalQualityResult(
            overall_quality=0.88,
            metrics=RetrievalQualityMetrics(
                coverage_score=0.85,
                relevance_score=0.90,
                diversity_score=0.85,
                completeness_score=0.90
            ),
            execution_time_ms=50,
            issues=[],
            suggestions=[]
        )

        answer_val = AnswerValidationResult(
            is_valid=True,
            overall_score=0.90,
            validation_details=AnswerValidationDetails(
                factual_consistency=0.92,
                hallucination_risk=0.08,
                citation_completeness=0.95,
                answer_quality=0.88,
                safety_score=1.0
            ),
            issues=[],
            action="approve",
            execution_time_ms=150,
            validation_method="fast_path"
        )

        report = orchestrate_quality(
            route_val,
            retrieval_qual,
            answer_val,
            {"total_time_ms": 2500, "retry_count": 0}
        )

        # Verify high quality output
        assert report.overall_confidence >= 0.85
        assert report.quality_level == "high"
        assert report.user_prompt is None
        assert report.breakdown.route_decision["score"] == 0.92
        assert report.breakdown.retrieval["score"] == 0.88
        assert report.breakdown.answer_factuality["score"] == 0.92
        assert report.breakdown.citations["score"] == 0.95

    def test_medium_quality_fusion(self):
        """Test fusion of medium quality scores"""
        route_val = RouteValidationResult(
            is_valid=True,
            confidence=0.75,
            validation_method="rule_feature",
            validation_reason="medium_confidence",
            execution_time_ms=15,
            warnings=[]
        )

        retrieval_qual = RetrievalQualityResult(
            overall_quality=0.72,
            metrics=RetrievalQualityMetrics(
                coverage_score=0.70,
                relevance_score=0.75,
                diversity_score=0.70,
                completeness_score=0.73
            ),
            execution_time_ms=60,
            issues=["Relevance could be improved"],
            suggestions=["Consider more specific keywords"]
        )

        answer_val = AnswerValidationResult(
            is_valid=True,
            overall_score=0.75,
            validation_details=AnswerValidationDetails(
                factual_consistency=0.78,
                hallucination_risk=0.15,
                citation_completeness=0.80,
                answer_quality=0.72,
                safety_score=1.0
            ),
            issues=[],
            action="approve",
            execution_time_ms=180,
            validation_method="standard"
        )

        report = orchestrate_quality(
            route_val,
            retrieval_qual,
            answer_val,
            {"total_time_ms": 3200, "retry_count": 0}
        )

        # Should be medium quality
        assert 0.70 <= report.overall_confidence < 0.85
        assert report.quality_level == "medium"
        assert report.user_prompt is not None
        assert "验证" in report.user_prompt

    def test_weighted_average_calculation(self):
        """Test exact weighted average calculation"""
        # Weights: route=0.15, retrieval=0.25, fact=0.40, quality=0.15, citation=0.05
        route_val = RouteValidationResult(
            is_valid=True, confidence=0.80, validation_method="rule_fast",
            validation_reason="test", execution_time_ms=10
        )

        retrieval_qual = RetrievalQualityResult(
            overall_quality=0.70,
            metrics=RetrievalQualityMetrics(
                coverage_score=0.7,
                relevance_score=0.7,
                diversity_score=0.7,
                completeness_score=0.7
            ),
            execution_time_ms=50
        )

        answer_val = AnswerValidationResult(
            is_valid=True, overall_score=0.75,
            validation_details=AnswerValidationDetails(
                factual_consistency=0.85,  # 40% weight
                hallucination_risk=0.10,
                citation_completeness=0.90,  # 5% weight
                answer_quality=0.75,  # 15% weight
                safety_score=1.0
            ),
            issues=[], action="approve",
            execution_time_ms=150, validation_method="fast_path"
        )

        report = orchestrate_quality(
            route_val, retrieval_qual, answer_val,
            {"total_time_ms": 2000}
        )

        # Expected: 0.80*0.15 + 0.70*0.25 + 0.85*0.40 + 0.75*0.15 + 0.90*0.05
        # = 0.12 + 0.175 + 0.34 + 0.1125 + 0.045 = 0.7925
        expected = 0.7925
        assert abs(report.overall_confidence - expected) < 0.01


class TestPenaltyRules:
    """Test penalty rules for hallucination and low route confidence"""

    def test_hallucination_penalty(self):
        """Test 0.7 multiplier for hallucination risk > 0.3"""
        route_val = RouteValidationResult(
            is_valid=True, confidence=0.85, validation_method="rule_fast",
            validation_reason="test", execution_time_ms=10
        )

        retrieval_qual = RetrievalQualityResult(
            overall_quality=0.80,
            metrics=RetrievalQualityMetrics(
                coverage_score=0.8,
                relevance_score=0.8,
                diversity_score=0.8,
                completeness_score=0.8
            ),
            execution_time_ms=50
        )

        answer_val = AnswerValidationResult(
            is_valid=True, overall_score=0.70,
            validation_details=AnswerValidationDetails(
                factual_consistency=0.65,
                hallucination_risk=0.35,  # > 0.3 threshold
                citation_completeness=0.70,
                answer_quality=0.75,
                safety_score=1.0
            ),
            issues=[],
            action="flag",
            execution_time_ms=200,
            validation_method="standard"
        )

        report = orchestrate_quality(
            route_val, retrieval_qual, answer_val,
            {"total_time_ms": 2500}
        )

        # Base score before penalty: 0.85*0.15 + 0.80*0.25 + 0.65*0.40 + 0.75*0.15 + 0.70*0.05
        # = 0.1275 + 0.2 + 0.26 + 0.1125 + 0.035 = 0.735
        # After 0.7 penalty: 0.735 * 0.7 = 0.5145
        assert report.overall_confidence < 0.60
        assert report.quality_level in ["low", "medium"]

    def test_low_route_confidence_penalty(self):
        """Test 0.8 multiplier for route confidence < 0.5"""
        route_val = RouteValidationResult(
            is_valid=True, confidence=0.45,  # < 0.5 threshold
            validation_method="llm",
            validation_reason="low_confidence",
            execution_time_ms=20,
            warnings=["Low confidence route"]
        )

        retrieval_qual = RetrievalQualityResult(
            overall_quality=0.85,
            metrics=RetrievalQualityMetrics(
                coverage_score=0.85,
                relevance_score=0.85,
                diversity_score=0.85,
                completeness_score=0.85
            ),
            execution_time_ms=50
        )

        answer_val = AnswerValidationResult(
            is_valid=True, overall_score=0.88,
            validation_details=AnswerValidationDetails(
                factual_consistency=0.90,
                hallucination_risk=0.08,
                citation_completeness=0.92,
                answer_quality=0.85,
                safety_score=1.0
            ),
            issues=[],
            action="approve",
            execution_time_ms=150,
            validation_method="fast_path"
        )

        report = orchestrate_quality(
            route_val, retrieval_qual, answer_val,
            {"total_time_ms": 2800}
        )

        # Base score: 0.45*0.15 + 0.85*0.25 + 0.90*0.40 + 0.85*0.15 + 0.92*0.05
        # = 0.0675 + 0.2125 + 0.36 + 0.1275 + 0.046 = 0.8135
        # After 0.8 penalty: 0.8135 * 0.8 = 0.6508
        assert report.overall_confidence < 0.80
        assert len(report.issues) > 0  # Should have route warning

    def test_both_penalties_applied(self):
        """Test both penalties applied together (0.7 * 0.8 = 0.56)"""
        route_val = RouteValidationResult(
            is_valid=True, confidence=0.48,  # < 0.5
            validation_method="llm",
            validation_reason="low_confidence",
            execution_time_ms=20
        )

        retrieval_qual = RetrievalQualityResult(
            overall_quality=0.75,
            metrics=RetrievalQualityMetrics(
                coverage_score=0.75,
                relevance_score=0.75,
                diversity_score=0.75,
                completeness_score=0.75
            ),
            execution_time_ms=60
        )

        answer_val = AnswerValidationResult(
            is_valid=True, overall_score=0.68,
            validation_details=AnswerValidationDetails(
                factual_consistency=0.70,
                hallucination_risk=0.32,  # > 0.3
                citation_completeness=0.75,
                answer_quality=0.70,
                safety_score=1.0
            ),
            issues=[],
            action="flag",
            execution_time_ms=200,
            validation_method="standard"
        )

        report = orchestrate_quality(
            route_val, retrieval_qual, answer_val,
            {"total_time_ms": 3000}
        )

        # Base: 0.48*0.15 + 0.75*0.25 + 0.70*0.40 + 0.70*0.15 + 0.75*0.05
        # = 0.072 + 0.1875 + 0.28 + 0.105 + 0.0375 = 0.682
        # After both penalties: 0.682 * 0.7 * 0.8 = 0.38192
        assert report.overall_confidence < 0.50
        assert report.quality_level == "very_low"
        assert "⚠️" in report.user_prompt


class TestIssueAggregation:
    """Test issue aggregation from all validators"""

    def test_aggregate_all_issues(self):
        """Test aggregation of issues from route, retrieval, and answer"""
        route_val = RouteValidationResult(
            is_valid=True, confidence=0.78, validation_method="rule_feature",
            validation_reason="test", execution_time_ms=15,
            warnings=["Route confidence borderline", "Consider fallback"]
        )

        retrieval_qual = RetrievalQualityResult(
            overall_quality=0.72,
            metrics=RetrievalQualityMetrics(
                coverage_score=0.7,
                relevance_score=0.75,
                diversity_score=0.7,
                completeness_score=0.73
            ),
            execution_time_ms=55,
            issues=["Low diversity in results", "Coverage gaps detected"],
            suggestions=["Expand search terms", "Try hybrid retrieval"]
        )

        answer_val = AnswerValidationResult(
            is_valid=True, overall_score=0.75,
            validation_details=AnswerValidationDetails(
                factual_consistency=0.78,
                hallucination_risk=0.18,
                citation_completeness=0.75,
                answer_quality=0.72,
                safety_score=1.0
            ),
            issues=[
                AnswerIssue(
                    type="missing_citation",
                    content="Claim about market share lacks citation reference",
                    severity="medium",
                    suggestion="Add citation to support claim",
                    location="paragraph_2"
                ),
                AnswerIssue(
                    type="unsupported_claim",
                    content="Statement about future trends not found in documents",
                    severity="high",
                    suggestion="Remove or qualify speculative statement",
                    location="paragraph_3"
                )
            ],
            action="flag",
            execution_time_ms=180,
            validation_method="standard"
        )

        report = orchestrate_quality(
            route_val, retrieval_qual, answer_val,
            {"total_time_ms": 3100, "retry_count": 0}
        )

        # Verify all issues aggregated
        assert len(report.issues) == 6  # 2 route + 2 retrieval + 2 answer

        # Check route issues
        route_issues = [i for i in report.issues if i["component"] == "route"]
        assert len(route_issues) == 2
        assert all(i["severity"] == "info" for i in route_issues)

        # Check retrieval issues
        retrieval_issues = [i for i in report.issues if i["component"] == "retrieval"]
        assert len(retrieval_issues) == 2

        # Check answer issues
        answer_issues = [i for i in report.issues if i["component"] == "answer"]
        assert len(answer_issues) == 2
        assert any(i["severity"] == "medium" for i in answer_issues)
        assert any(i["severity"] == "high" for i in answer_issues)

        # Verify suggestions
        assert len(report.suggestions) == 2
        assert "Expand search terms" in report.suggestions

    def test_no_issues(self):
        """Test report with no issues"""
        route_val = RouteValidationResult(
            is_valid=True, confidence=0.92, validation_method="rule_fast",
            validation_reason="high_confidence", execution_time_ms=10
        )

        retrieval_qual = RetrievalQualityResult(
            overall_quality=0.88,
            metrics=RetrievalQualityMetrics(
                coverage_score=0.88,
                relevance_score=0.90,
                diversity_score=0.85,
                completeness_score=0.87
            ),
            execution_time_ms=50
        )

        answer_val = AnswerValidationResult(
            is_valid=True, overall_score=0.92,
            validation_details=AnswerValidationDetails(
                factual_consistency=0.95,
                hallucination_risk=0.05,
                citation_completeness=0.98,
                answer_quality=0.90,
                safety_score=1.0
            ),
            issues=[],
            action="approve",
            execution_time_ms=140,
            validation_method="fast_path"
        )

        report = orchestrate_quality(
            route_val, retrieval_qual, answer_val,
            {"total_time_ms": 2300}
        )

        assert len(report.issues) == 0
        assert len(report.suggestions) == 0


class TestExecutionStats:
    """Test execution statistics calculation"""

    def test_execution_stats_calculation(self):
        """Test proper calculation of validation overhead"""
        route_val = RouteValidationResult(
            is_valid=True, confidence=0.85, validation_method="rule_fast",
            validation_reason="test", execution_time_ms=12
        )

        retrieval_qual = RetrievalQualityResult(
            overall_quality=0.80,
            metrics=RetrievalQualityMetrics(
                coverage_score=0.8,
                relevance_score=0.8,
                diversity_score=0.8,
                completeness_score=0.8
            ),
            execution_time_ms=58
        )

        answer_val = AnswerValidationResult(
            is_valid=True, overall_score=0.85,
            validation_details=AnswerValidationDetails(
                factual_consistency=0.88,
                hallucination_risk=0.10,
                citation_completeness=0.90,
                answer_quality=0.82,
                safety_score=1.0
            ),
            issues=[],
            action="approve",
            execution_time_ms=165,
            validation_method="standard"
        )

        report = orchestrate_quality(
            route_val, retrieval_qual, answer_val,
            {
                "total_time_ms": 2850,
                "retry_count": 1,
                "route_retry": 0,
                "answer_retry": 1
            }
        )

        # Verify execution stats
        assert report.execution_stats.total_time_ms == 2850
        assert report.execution_stats.validation_overhead_ms == 235  # 12 + 58 + 165
        assert report.execution_stats.retry_count == 1
        assert report.execution_stats.route_retry == 0
        assert report.execution_stats.answer_retry == 1


class TestPerformance:
    """Test performance target of <5ms"""

    def test_execution_time_under_5ms(self):
        """Test orchestration completes in <5ms"""
        route_val = RouteValidationResult(
            is_valid=True, confidence=0.85, validation_method="rule_fast",
            validation_reason="test", execution_time_ms=10
        )

        retrieval_qual = RetrievalQualityResult(
            overall_quality=0.80,
            metrics=RetrievalQualityMetrics(
                coverage_score=0.8,
                relevance_score=0.8,
                diversity_score=0.8,
                completeness_score=0.8
            ),
            execution_time_ms=50
        )

        answer_val = AnswerValidationResult(
            is_valid=True, overall_score=0.85,
            validation_details=AnswerValidationDetails(
                factual_consistency=0.88,
                hallucination_risk=0.10,
                citation_completeness=0.90,
                answer_quality=0.82,
                safety_score=1.0
            ),
            issues=[],
            action="approve",
            execution_time_ms=150,
            validation_method="fast_path"
        )

        # Run 10 times and measure average
        times = []
        for _ in range(10):
            start = time.perf_counter()
            report = orchestrate_quality(
                route_val, retrieval_qual, answer_val,
                {"total_time_ms": 2500}
            )
            elapsed = (time.perf_counter() - start) * 1000  # Convert to ms
            times.append(elapsed)

        avg_time = sum(times) / len(times)
        max_time = max(times)

        # Should be well under 5ms
        assert avg_time < 5.0, f"Average time {avg_time:.2f}ms exceeds 5ms target"
        assert max_time < 5.0, f"Max time {max_time:.2f}ms exceeds 5ms target"

        # Verify result correctness
        assert report.overall_confidence > 0
        assert report.quality_level in ["high", "medium", "low", "very_low"]


class TestBreakdownGeneration:
    """Test quality breakdown generation"""

    def test_breakdown_structure(self):
        """Test breakdown contains all required components with correct status"""
        route_val = RouteValidationResult(
            is_valid=True, confidence=0.88, validation_method="rule_fast",
            validation_reason="high_confidence", execution_time_ms=10
        )

        retrieval_qual = RetrievalQualityResult(
            overall_quality=0.75,
            metrics=RetrievalQualityMetrics(
                coverage_score=0.75,
                relevance_score=0.75,
                diversity_score=0.75,
                completeness_score=0.75
            ),
            execution_time_ms=55
        )

        answer_val = AnswerValidationResult(
            is_valid=True, overall_score=0.82,
            validation_details=AnswerValidationDetails(
                factual_consistency=0.85,
                hallucination_risk=0.12,
                citation_completeness=0.88,
                answer_quality=0.78,
                safety_score=1.0
            ),
            issues=[],
            action="approve",
            execution_time_ms=160,
            validation_method="standard"
        )

        report = orchestrate_quality(
            route_val, retrieval_qual, answer_val,
            {"total_time_ms": 2700}
        )

        # Verify breakdown structure
        breakdown = report.breakdown

        assert "score" in breakdown.route_decision
        assert "status" in breakdown.route_decision
        assert breakdown.route_decision["score"] == 0.88
        assert "✓" in breakdown.route_decision["status"]

        assert "score" in breakdown.retrieval
        assert "status" in breakdown.retrieval
        assert breakdown.retrieval["score"] == 0.75
        assert "✓" in breakdown.retrieval["status"]

        assert "score" in breakdown.answer_factuality
        assert "status" in breakdown.answer_factuality
        assert breakdown.answer_factuality["score"] == 0.85
        assert "✓" in breakdown.answer_factuality["status"]

        assert "score" in breakdown.citations
        assert "status" in breakdown.citations
        assert breakdown.citations["score"] == 0.88
        assert "✓" in breakdown.citations["status"]

    def test_breakdown_warning_status(self):
        """Test breakdown shows warnings for low scores"""
        route_val = RouteValidationResult(
            is_valid=False, confidence=0.55, validation_method="llm",
            validation_reason="low_confidence", execution_time_ms=20
        )

        retrieval_qual = RetrievalQualityResult(
            overall_quality=0.62,
            metrics=RetrievalQualityMetrics(
                coverage_score=0.6,
                relevance_score=0.65,
                diversity_score=0.6,
                completeness_score=0.63
            ),
            execution_time_ms=60
        )

        answer_val = AnswerValidationResult(
            is_valid=True, overall_score=0.72,
            validation_details=AnswerValidationDetails(
                factual_consistency=0.75,
                hallucination_risk=0.20,
                citation_completeness=0.72,
                answer_quality=0.70,
                safety_score=1.0
            ),
            issues=[],
            action="flag",
            execution_time_ms=190,
            validation_method="standard"
        )

        report = orchestrate_quality(
            route_val, retrieval_qual, answer_val,
            {"total_time_ms": 3200}
        )

        # Should show warnings for low scores
        assert "⚠" in report.breakdown.route_decision["status"]
        assert "⚠" in report.breakdown.retrieval["status"]
        assert "⚠" in report.breakdown.citations["status"]


class TestEdgeCases:
    """Test edge cases and boundary conditions"""

    def test_zero_confidence_scores(self):
        """Test handling of zero confidence scores"""
        route_val = RouteValidationResult(
            is_valid=False, confidence=0.0, validation_method="llm",
            validation_reason="failed", execution_time_ms=20
        )

        retrieval_qual = RetrievalQualityResult(
            overall_quality=0.0,
            metrics=RetrievalQualityMetrics(
                coverage_score=0.0,
                relevance_score=0.0,
                diversity_score=0.0,
                completeness_score=0.0
            ),
            execution_time_ms=50
        )

        answer_val = AnswerValidationResult(
            is_valid=False, overall_score=0.0,
            validation_details=AnswerValidationDetails(
                factual_consistency=0.0,
                hallucination_risk=1.0,
                citation_completeness=0.0,
                answer_quality=0.0,
                safety_score=0.0
            ),
            issues=[],
            action="regenerate",
            execution_time_ms=100,
            validation_method="deep"
        )

        report = orchestrate_quality(
            route_val, retrieval_qual, answer_val,
            {"total_time_ms": 3500}
        )

        # Should be very low quality
        assert report.overall_confidence == 0.0
        assert report.quality_level == "very_low"
        assert report.user_prompt is not None

    def test_perfect_scores(self):
        """Test handling of perfect 1.0 scores"""
        route_val = RouteValidationResult(
            is_valid=True, confidence=1.0, validation_method="cache",
            validation_reason="cached", execution_time_ms=2
        )

        retrieval_qual = RetrievalQualityResult(
            overall_quality=1.0,
            metrics=RetrievalQualityMetrics(
                coverage_score=1.0,
                relevance_score=1.0,
                diversity_score=1.0,
                completeness_score=1.0
            ),
            execution_time_ms=30
        )

        answer_val = AnswerValidationResult(
            is_valid=True, overall_score=1.0,
            validation_details=AnswerValidationDetails(
                factual_consistency=1.0,
                hallucination_risk=0.0,
                citation_completeness=1.0,
                answer_quality=1.0,
                safety_score=1.0
            ),
            issues=[],
            action="approve",
            execution_time_ms=100,
            validation_method="fast_path"
        )

        report = orchestrate_quality(
            route_val, retrieval_qual, answer_val,
            {"total_time_ms": 1800}
        )

        # Should be high quality
        assert report.overall_confidence == 1.0
        assert report.quality_level == "high"
        assert report.user_prompt is None

    def test_missing_optional_metadata(self):
        """Test handling of missing optional execution metadata"""
        route_val = RouteValidationResult(
            is_valid=True, confidence=0.85, validation_method="rule_fast",
            validation_reason="test", execution_time_ms=10
        )

        retrieval_qual = RetrievalQualityResult(
            overall_quality=0.80,
            metrics=RetrievalQualityMetrics(
                coverage_score=0.8,
                relevance_score=0.8,
                diversity_score=0.8,
                completeness_score=0.8
            ),
            execution_time_ms=50
        )

        answer_val = AnswerValidationResult(
            is_valid=True, overall_score=0.85,
            validation_details=AnswerValidationDetails(
                factual_consistency=0.88,
                hallucination_risk=0.10,
                citation_completeness=0.90,
                answer_quality=0.82,
                safety_score=1.0
            ),
            issues=[],
            action="approve",
            execution_time_ms=150,
            validation_method="fast_path"
        )

        # Call with minimal metadata
        report = orchestrate_quality(
            route_val, retrieval_qual, answer_val,
            {}  # Empty metadata
        )

        # Should handle missing fields gracefully
        assert report.execution_stats.total_time_ms == 0
        assert report.execution_stats.retry_count == 0
        assert report.execution_stats.route_retry == 0
        assert report.execution_stats.answer_retry == 0
        assert report.overall_confidence > 0
