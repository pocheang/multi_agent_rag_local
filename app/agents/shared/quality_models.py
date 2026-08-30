"""
Pydantic models for quality assurance agents.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field

# ============================================================================
# Route Validation Models
# ============================================================================


class RouteValidationResult(BaseModel):
    """Route validation result from Route Validator Agent"""

    is_valid: bool
    confidence: float = Field(ge=0.0, le=1.0)
    validation_method: Literal["rule_fast", "rule_feature", "llm", "cache"]
    validation_reason: str
    execution_time_ms: int
    suggested_alternative: dict[str, str] | None = None
    warnings: list[str] = Field(default_factory=list)


# ============================================================================
# Retrieval Quality Models
# ============================================================================


class RetrievalQualityMetrics(BaseModel):
    """Individual retrieval quality metrics"""

    coverage_score: float = Field(ge=0.0, le=1.0)
    relevance_score: float = Field(ge=0.0, le=1.0)
    diversity_score: float = Field(ge=0.0, le=1.0)
    completeness_score: float = Field(ge=0.0, le=1.0)


class RetrievalQualityResult(BaseModel):
    """Retrieval quality assessment result"""

    overall_quality: float = Field(ge=0.0, le=1.0)
    metrics: RetrievalQualityMetrics
    execution_time_ms: int
    issues: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)


# ============================================================================
# Answer Validation Models
# ============================================================================


class AnswerValidationDetails(BaseModel):
    """Detailed answer validation metrics"""

    factual_consistency: float = Field(ge=0.0, le=1.0)
    hallucination_risk: float = Field(ge=0.0, le=1.0)
    citation_completeness: float = Field(ge=0.0, le=1.0)
    answer_quality: float = Field(ge=0.0, le=1.0)
    safety_score: float = Field(ge=0.0, le=1.0)


class AnswerIssue(BaseModel):
    """Individual answer issue"""

    type: Literal["unsupported_claim", "missing_citation", "hallucination", "safety", "quality"]
    content: str
    severity: Literal["low", "medium", "high", "critical"]
    suggestion: str
    location: str | None = None


class AnswerValidationResult(BaseModel):
    """Answer validation result from Answer Validator Agent"""

    is_valid: bool
    overall_score: float = Field(ge=0.0, le=1.0)
    validation_details: AnswerValidationDetails
    issues: list[AnswerIssue] = Field(default_factory=list)
    action: Literal["approve", "flag", "regenerate"]
    execution_time_ms: int
    validation_method: Literal["fast_path", "standard", "deep"]


# ============================================================================
# Quality Orchestration Models
# ============================================================================


class QualityBreakdown(BaseModel):
    """Quality score breakdown by component"""

    route_decision: dict[str, Any]
    retrieval: dict[str, Any]
    answer_factuality: dict[str, Any]
    citations: dict[str, Any]


class ExecutionStats(BaseModel):
    """Execution statistics"""

    total_time_ms: int
    validation_overhead_ms: int
    retry_count: int
    route_retry: int = 0
    answer_retry: int = 0


class QualityReport(BaseModel):
    """Comprehensive quality report from Quality Orchestrator"""

    overall_confidence: float = Field(ge=0.0, le=1.0)
    quality_level: Literal["high", "medium", "low", "very_low"]
    quality_label: str
    user_prompt: str | None = None
    breakdown: QualityBreakdown
    issues: list[dict[str, str]] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    execution_stats: ExecutionStats
