"""
Unit tests for query optimization service.
"""

import pytest

from app.services.query_optimization import (
    QualityAnalyzer,
    QueryQuality,
    SuggestionGenerator,
    ExampleBuilder,
    OptimizationSuggestion,
    QueryOptimizationService,
)


# ============================================================================
# QualityAnalyzer Tests
# ============================================================================

class TestQualityAnalyzer:
    """Test QualityAnalyzer component."""

    def test_high_quality_query(self):
        """Test high-quality query detection."""
        analyzer = QualityAnalyzer()
        result = analyzer.analyze("公司2023年第一季度的营收增长率相比去年同期有何变化？")

        assert result.level == "high"
        assert result.score >= 80
        assert len(result.issues) == 0

    def test_very_short_query(self):
        """Test very short query detection."""
        analyzer = QualityAnalyzer()
        result = analyzer.analyze("公司")

        assert result.level in ("low", "very_low")
        assert "query_too_short" in result.issues
        assert result.details["length"] < 70

    def test_vague_query(self):
        """Test vague language detection."""
        analyzer = QualityAnalyzer()
        result = analyzer.analyze("公司情况怎么样")

        assert result.level in ("low", "very_low", "medium")
        assert "vague_language" in result.issues
        assert result.details["vagueness"] <= 70

    def test_missing_time_dimension(self):
        """Test missing time dimension detection."""
        analyzer = QualityAnalyzer()
        result = analyzer.analyze("公司的营收增长率")

        assert "missing_time_dimension" in result.issues

    def test_with_time_dimension(self):
        """Test query with time dimension."""
        analyzer = QualityAnalyzer()
        result = analyzer.analyze("公司2023年的营收增长率")

        assert "missing_time_dimension" not in result.issues

    def test_unclear_subject(self):
        """Test unclear subject detection."""
        analyzer = QualityAnalyzer()
        result = analyzer.analyze("情况如何")

        assert "unclear_subject" in result.issues

    def test_clear_subject(self):
        """Test clear subject detection."""
        analyzer = QualityAnalyzer()
        result = analyzer.analyze("苹果公司的市场份额")

        assert "unclear_subject" not in result.issues

    def test_unclear_intent(self):
        """Test unclear intent detection."""
        analyzer = QualityAnalyzer()
        result = analyzer.analyze("公司的事情")

        assert "unclear_intent" in result.issues

    def test_clear_intent(self):
        """Test clear intent detection."""
        analyzer = QualityAnalyzer()
        result = analyzer.analyze("分析公司的财务风险")

        assert "unclear_intent" not in result.issues

    def test_english_query(self):
        """Test English query analysis."""
        analyzer = QualityAnalyzer()
        result = analyzer.analyze("What is the company's revenue growth in 2023 Q1?")

        assert result.level in ("high", "medium")
        assert result.score >= 60


# ============================================================================
# SuggestionGenerator Tests
# ============================================================================

class TestSuggestionGenerator:
    """Test SuggestionGenerator component."""

    def test_high_quality_no_suggestion(self):
        """Test no suggestion for high-quality query."""
        generator = SuggestionGenerator()
        quality = QueryQuality(
            score=85.0,
            level="high",
            issues=(),
            details={},
        )

        result = generator.generate("test query", quality)

        assert len(result.clarifications) == 0
        assert len(result.examples) == 0
        assert "良好" in result.reasoning

    def test_suggestion_for_short_query(self):
        """Test suggestion generation for short query."""
        generator = SuggestionGenerator()
        quality = QueryQuality(
            score=45.0,
            level="low",
            issues=("query_too_short",),
            details={},
        )

        result = generator.generate("公司", quality)

        assert len(result.clarifications) > 0
        assert any("背景" in c or "细节" in c for c in result.clarifications)

    def test_suggestion_for_vague_query(self):
        """Test suggestion generation for vague query."""
        generator = SuggestionGenerator()
        quality = QueryQuality(
            score=50.0,
            level="low",
            issues=("vague_language",),
            details={},
        )

        result = generator.generate("情况怎么样", quality)

        assert len(result.clarifications) > 0
        assert any("具体" in c or "明确" in c for c in result.clarifications)

    def test_suggestion_for_missing_time(self):
        """Test suggestion generation for missing time dimension."""
        generator = SuggestionGenerator()
        quality = QueryQuality(
            score=60.0,
            level="medium",
            issues=("missing_time_dimension",),
            details={},
        )

        result = generator.generate("公司营收", quality)

        assert len(result.clarifications) > 0
        assert any("时间" in c for c in result.clarifications)

    def test_reasoning_for_very_low_quality(self):
        """Test reasoning for very low quality query."""
        generator = SuggestionGenerator()
        quality = QueryQuality(
            score=30.0,
            level="very_low",
            issues=("query_too_short", "vague_language"),
            details={},
        )

        result = generator.generate("啥", quality)

        assert "模糊" in result.reasoning or "不够" in result.reasoning


# ============================================================================
# ExampleBuilder Tests
# ============================================================================

class TestExampleBuilder:
    """Test ExampleBuilder component."""

    def test_build_examples_with_time_suggestion(self):
        """Test example building with time dimension suggestion."""
        builder = ExampleBuilder()
        suggestion = OptimizationSuggestion(
            clarifications=("明确时间范围 (例: 2023年、最近一季度)",),
            examples=(),
            reasoning="test",
        )

        result = builder.build_examples("公司营收", suggestion)

        assert len(result) > 0
        assert any("2023" in ex or "季度" in ex for ex in result)

    def test_build_examples_with_specificity_suggestion(self):
        """Test example building with specificity suggestion."""
        builder = ExampleBuilder()
        suggestion = OptimizationSuggestion(
            clarifications=("指定具体的主体或对象",),
            examples=(),
            reasoning="test",
        )

        result = builder.build_examples("业务情况", suggestion)

        assert len(result) > 0
        assert any("指标" in ex or "竞争" in ex for ex in result)

    def test_build_examples_with_intent_suggestion(self):
        """Test example building with intent suggestion."""
        builder = ExampleBuilder()
        suggestion = OptimizationSuggestion(
            clarifications=("明确查询目的",),
            examples=(),
            reasoning="test",
        )

        result = builder.build_examples("公司", suggestion)

        assert len(result) > 0
        assert any("分析" in ex or "风险" in ex for ex in result)

    def test_max_three_examples(self):
        """Test that at most 3 examples are returned."""
        builder = ExampleBuilder()
        suggestion = OptimizationSuggestion(
            clarifications=(
                "明确时间范围",
                "指定具体主体",
                "明确查询目的",
                "使用完整问句",
            ),
            examples=(),
            reasoning="test",
        )

        result = builder.build_examples("公司", suggestion)

        assert len(result) <= 3

    def test_fallback_examples(self):
        """Test fallback examples when no specific suggestions."""
        builder = ExampleBuilder()
        suggestion = OptimizationSuggestion(
            clarifications=("其他建议",),
            examples=(),
            reasoning="test",
        )

        result = builder.build_examples("测试", suggestion)

        assert len(result) > 0


# ============================================================================
# QueryOptimizationService Tests
# ============================================================================

class TestQueryOptimizationService:
    """Test QueryOptimizationService integration."""

    def test_analyze_and_suggest_high_quality(self):
        """Test service with high-quality query."""
        service = QueryOptimizationService()
        quality, suggestion = service.analyze_and_suggest(
            "公司2023年第一季度的营收增长率相比去年同期有何变化？"
        )

        assert quality.level == "high"
        assert len(suggestion.clarifications) == 0

    def test_analyze_and_suggest_low_quality(self):
        """Test service with low-quality query."""
        service = QueryOptimizationService()
        quality, suggestion = service.analyze_and_suggest("公司情况")

        assert quality.level in ("low", "very_low")
        assert len(suggestion.clarifications) > 0
        assert len(suggestion.examples) > 0

    def test_analyze_and_suggest_medium_quality(self):
        """Test service with medium-quality query."""
        service = QueryOptimizationService()
        quality, suggestion = service.analyze_and_suggest("公司的营收增长")

        assert quality.level in ("medium", "low")
        assert len(suggestion.clarifications) > 0

    def test_examples_generated(self):
        """Test that examples are generated in the service."""
        service = QueryOptimizationService()
        quality, suggestion = service.analyze_and_suggest("公司")

        # Low quality query should have suggestions and examples
        if quality.level in ("low", "very_low"):
            assert len(suggestion.examples) > 0

    def test_custom_components(self):
        """Test service with custom components."""
        analyzer = QualityAnalyzer()
        generator = SuggestionGenerator()
        builder = ExampleBuilder()

        service = QueryOptimizationService(
            analyzer=analyzer,
            suggestion_generator=generator,
            example_builder=builder,
        )

        quality, suggestion = service.analyze_and_suggest("测试查询")

        assert isinstance(quality, QueryQuality)
        assert isinstance(suggestion, OptimizationSuggestion)


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_query(self):
        """Test empty query handling."""
        analyzer = QualityAnalyzer()
        result = analyzer.analyze("")

        assert result.level == "very_low"
        assert result.score < 50

    def test_whitespace_only_query(self):
        """Test whitespace-only query."""
        analyzer = QualityAnalyzer()
        result = analyzer.analyze("   ")

        assert result.level == "very_low"

    def test_very_long_query(self):
        """Test very long query (should still be acceptable)."""
        analyzer = QualityAnalyzer()
        long_query = "公司" + "的营收情况" * 50
        result = analyzer.analyze(long_query)

        # Long query should still get reasonable score if it has content
        assert result.score > 0

    def test_mixed_language_query(self):
        """Test query with mixed Chinese and English."""
        analyzer = QualityAnalyzer()
        result = analyzer.analyze("What is the 公司 revenue in 2023?")

        assert result.score > 0
        assert result.level in ("high", "medium", "low")

    def test_query_with_numbers(self):
        """Test query with numbers and specific data."""
        analyzer = QualityAnalyzer()
        result = analyzer.analyze("2023年Q1营收相比2022年Q1增长了多少？")

        assert result.level in ("high", "medium")
        assert "missing_time_dimension" not in result.issues
