"""
Query optimization suggestion system.

Detects vague or low-quality queries and provides actionable suggestions
to help users refine their questions for better answers.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

__all__ = [
    "QueryQuality",
    "OptimizationSuggestion",
    "QualityAnalyzer",
    "SuggestionGenerator",
    "ExampleBuilder",
    "QueryOptimizationService",
]


# ============================================================================
# Data Models
# ============================================================================


@dataclass
class QueryQuality:
    """Query quality assessment result."""

    score: float  # 0-100
    level: Literal["high", "medium", "low", "very_low"]
    issues: tuple[str, ...]  # Detected issues
    details: dict[str, float]  # Detailed scores by dimension


@dataclass
class OptimizationSuggestion:
    """Query optimization suggestion."""

    clarifications: tuple[str, ...]  # Aspects to clarify
    examples: tuple[str, ...]  # Optimized query examples
    reasoning: str  # Why optimization is needed


# ============================================================================
# Quality Analyzer
# ============================================================================


class QualityAnalyzer:
    """Analyze query quality and detect issues."""

    # Vague keywords that indicate unclear queries
    VAGUE_WORDS_ZH = frozenset(
        [
            "情况",
            "怎么样",
            "如何",
            "什么",
            "有哪些",
            "介绍",
            "说说",
            "讲讲",
            "了解",
            "知道",
        ]
    )

    VAGUE_WORDS_EN = frozenset(
        [
            "situation",
            "status",
            "how",
            "what",
            "about",
            "tell me",
            "explain",
            "describe",
            "information",
        ]
    )

    # Overly broad terms
    BROAD_TERMS = frozenset(
        [
            "所有",
            "全部",
            "各种",
            "任何",
            "整个",
            "all",
            "every",
            "any",
            "entire",
            "whole",
        ]
    )

    def analyze(self, query: str) -> QueryQuality:
        """
        Analyze query quality across multiple dimensions.

        Args:
            query: User query string

        Returns:
            QueryQuality with score, level, and detected issues
        """
        query_clean = query.strip()

        # Handle empty or near-empty queries immediately
        if len(query_clean) < 2:
            return QueryQuality(
                score=0.0,
                level="very_low",
                issues=("query_too_short", "unclear_subject", "unclear_intent"),
                details={
                    "length": 0.0,
                    "vagueness": 0.0,
                    "specificity": 0.0,
                    "structure": 0.0,
                },
            )

        # Initialize scores
        length_score = self._check_length(query_clean)
        vagueness_score = self._check_vagueness(query_clean)
        specificity_score = self._check_specificity(query_clean)
        structure_score = self._check_structure(query_clean)

        # Weighted average
        score = length_score * 0.2 + vagueness_score * 0.3 + specificity_score * 0.3 + structure_score * 0.2

        # Apply penalty for very short queries (< 5 chars)
        # These are almost always low quality regardless of other factors
        if len(query_clean) < 5:
            score = min(score, 50.0)  # Cap at 50 for very short queries

        # Determine level
        if score >= 80:
            level = "high"
        elif score >= 60:
            level = "medium"
        elif score >= 40:
            level = "low"
        else:
            level = "very_low"

        # Collect issues
        issues = self._identify_issues(
            query_clean,
            length_score,
            vagueness_score,
            specificity_score,
            structure_score,
        )

        return QueryQuality(
            score=score,
            level=level,
            issues=issues,
            details={
                "length": length_score,
                "vagueness": vagueness_score,
                "specificity": specificity_score,
                "structure": structure_score,
            },
        )

    def _check_length(self, query: str) -> float:
        """Check if query length is appropriate."""
        length = len(query)

        if length < 5:
            return 40.0  # Too short
        elif length < 10:
            return 70.0  # Short but acceptable
        elif length <= 100:
            return 100.0  # Good length
        elif length <= 200:
            return 90.0  # Slightly long
        else:
            return 80.0  # Very long

    def _check_vagueness(self, query: str) -> float:
        """Check for vague language."""
        query_lower = query.lower()
        score = 100.0

        # Check vague words
        vague_count = sum(1 for word in self.VAGUE_WORDS_ZH | self.VAGUE_WORDS_EN if word in query_lower)
        score -= min(vague_count * 15, 45)  # Max -45 for vague words

        # Check overly broad terms
        broad_count = sum(1 for term in self.BROAD_TERMS if term in query_lower)
        score -= min(broad_count * 10, 30)  # Max -30 for broad terms

        return max(score, 0.0)

    def _check_specificity(self, query: str) -> float:
        """Check if query has specific elements."""
        score = 100.0

        # Check for time dimension
        has_time = self._has_time_reference(query)
        if not has_time:
            score -= 20

        # Check for specific subject
        has_subject = self._has_specific_subject(query)
        if not has_subject:
            score -= 20

        # Check for clear intent
        has_intent = self._has_clear_intent(query)
        if not has_intent:
            score -= 15

        return max(score, 0.0)

    def _check_structure(self, query: str) -> float:
        """Check query structure quality."""
        score = 100.0

        # Check if it's a complete sentence
        if not query.endswith(("？", "?", "。", ".")):
            score -= 10

        # Check if it has meaningful structure
        if len(query.split()) < 2:
            score -= 15

        return max(score, 0.0)

    def _has_time_reference(self, query: str) -> bool:
        """Check if query mentions time."""
        time_indicators = [
            # Chinese
            "年",
            "月",
            "日",
            "季度",
            "最近",
            "今年",
            "去年",
            "同比",
            "环比",
            "当前",
            "过去",
            "未来",
            # English
            "year",
            "month",
            "quarter",
            "recent",
            "current",
            "last",
            "this",
            "past",
            "future",
            "today",
        ]
        return any(indicator in query.lower() for indicator in time_indicators)

    def _has_specific_subject(self, query: str) -> bool:
        """Check if query has a specific subject."""
        # If query is too short, likely no specific subject
        if len(query) < 8:
            return False

        # If query contains only vague words, no specific subject
        query_lower = query.lower()
        vague_only = all(word in query_lower for word in self.VAGUE_WORDS_ZH | self.VAGUE_WORDS_EN if len(word) > 2)
        if vague_only:
            return False

        return True

    def _has_clear_intent(self, query: str) -> bool:
        """Check if query has clear intent."""
        intent_indicators = [
            # Analysis
            "分析",
            "比较",
            "评估",
            "判断",
            "analyze",
            "compare",
            "evaluate",
            # Information
            "多少",
            "数据",
            "指标",
            "趋势",
            "how much",
            "data",
            "metrics",
            "trend",
            # Explanation
            "为什么",
            "原因",
            "影响",
            "导致",
            "why",
            "reason",
            "impact",
            "cause",
        ]
        return any(indicator in query.lower() for indicator in intent_indicators)

    def _identify_issues(
        self,
        query: str,
        length_score: float,
        vagueness_score: float,
        specificity_score: float,
        structure_score: float,
    ) -> tuple[str, ...]:
        """Identify specific issues with the query."""
        issues = []

        if length_score < 70:
            issues.append("query_too_short")

        if vagueness_score <= 70:  # Changed from < to <= to catch boundary case
            issues.append("vague_language")

        if specificity_score < 70:
            if not self._has_time_reference(query):
                issues.append("missing_time_dimension")
            if not self._has_specific_subject(query):
                issues.append("unclear_subject")
            if not self._has_clear_intent(query):
                issues.append("unclear_intent")

        if structure_score < 80:
            issues.append("incomplete_structure")

        return tuple(issues)


# ============================================================================
# Suggestion Generator
# ============================================================================


class SuggestionGenerator:
    """Generate optimization suggestions based on query issues."""

    def generate(
        self,
        query: str,
        quality: QueryQuality,
    ) -> OptimizationSuggestion:
        """
        Generate optimization suggestions.

        Args:
            query: Original query
            quality: Quality assessment result

        Returns:
            OptimizationSuggestion with clarifications and reasoning
        """
        if quality.level == "high":
            # Query is already good
            return OptimizationSuggestion(
                clarifications=(),
                examples=(),
                reasoning="查询质量良好，无需优化",
            )

        clarifications = self._build_clarifications(quality.issues)
        reasoning = self._build_reasoning(quality)

        return OptimizationSuggestion(
            clarifications=clarifications,
            examples=(),  # Will be filled by ExampleBuilder
            reasoning=reasoning,
        )

    def _build_clarifications(self, issues: tuple[str, ...]) -> tuple[str, ...]:
        """Build clarification suggestions based on issues."""
        suggestions = []

        if "query_too_short" in issues:
            suggestions.append("提供更多背景信息和具体细节")

        if "vague_language" in issues:
            suggestions.append("使用更具体、明确的词语")

        if "missing_time_dimension" in issues:
            suggestions.append("明确时间范围 (例: 2023年、最近一季度、同比)")

        if "unclear_subject" in issues:
            suggestions.append("指定具体的主体或对象 (例: 某个产品、部门、指标)")

        if "unclear_intent" in issues:
            suggestions.append("明确查询目的 (例: 了解现状、分析趋势、找出原因)")

        if "incomplete_structure" in issues:
            suggestions.append("使用完整的问句结构")

        return tuple(suggestions)

    def _build_reasoning(self, quality: QueryQuality) -> str:
        """Build reasoning for why optimization is needed."""
        if quality.level == "very_low":
            return "您的问题过于模糊，系统可能无法提供准确的答案。建议您按照提示优化问题。"
        elif quality.level == "low":
            return "您的问题不够具体，可能会得到泛泛的答案。建议适当补充细节。"
        elif quality.level == "medium":
            return "您的问题基本清晰，但仍有改进空间。补充一些细节会得到更精准的答案。"
        else:
            return "您的问题表述清晰。"


# ============================================================================
# Example Builder
# ============================================================================


class ExampleBuilder:
    """Build optimized query examples."""

    def build_examples(
        self,
        query: str,
        suggestion: OptimizationSuggestion,
    ) -> tuple[str, ...]:
        """
        Build optimized query examples.

        Args:
            query: Original query
            suggestion: Optimization suggestion

        Returns:
            Tuple of optimized query examples
        """
        # Extract base intent
        base = self._extract_base_intent(query)

        examples = []

        # Add time dimension if missing
        if any("时间" in c or "time" in c.lower() for c in suggestion.clarifications):
            examples.append(f"{base}在2023年的情况？")
            examples.append(f"{base}最近一季度的变化？")

        # Add specificity if missing
        if any("具体" in c or "specific" in c.lower() for c in suggestion.clarifications):
            examples.append(f"{base}的主要指标是什么？")
            examples.append(f"{base}与竞争对手相比如何？")

        # Add intent if missing
        if any("目的" in c or "intent" in c.lower() for c in suggestion.clarifications):
            examples.append(f"分析{base}的发展趋势")
            examples.append(f"{base}存在哪些风险？")

        # Fallback: generic improvements
        if not examples:
            examples.append(f"{base}的详细情况是什么？")
            examples.append(f"请具体说明{base}")

        return tuple(examples[:3])  # Return max 3 examples

    def _extract_base_intent(self, query: str) -> str:
        """Extract base intent from query."""
        # Remove common vague endings
        query = query.strip()
        for ending in ["？", "?", "情况", "怎么样", "如何"]:
            query = query.rstrip(ending)

        return query.strip() or "相关信息"


# ============================================================================
# Main Service
# ============================================================================


class QueryOptimizationService:
    """Main service for query optimization."""

    def __init__(
        self,
        analyzer: QualityAnalyzer | None = None,
        suggestion_generator: SuggestionGenerator | None = None,
        example_builder: ExampleBuilder | None = None,
    ):
        self.analyzer = analyzer or QualityAnalyzer()
        self.suggestion_generator = suggestion_generator or SuggestionGenerator()
        self.example_builder = example_builder or ExampleBuilder()

    def analyze_and_suggest(self, query: str) -> tuple[QueryQuality, OptimizationSuggestion]:
        """
        Analyze query and generate suggestions in one call.

        Args:
            query: User query

        Returns:
            Tuple of (quality assessment, optimization suggestion)
        """
        # Step 1: Analyze quality
        quality = self.analyzer.analyze(query)

        # Step 2: Generate suggestions
        suggestion = self.suggestion_generator.generate(query, quality)

        # Step 3: Build examples
        if suggestion.clarifications:
            examples = self.example_builder.build_examples(query, suggestion)
            suggestion = OptimizationSuggestion(
                clarifications=suggestion.clarifications,
                examples=examples,
                reasoning=suggestion.reasoning,
            )

        return quality, suggestion
