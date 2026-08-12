"""
Pydantic models for quality assurance agents.
"""

from pydantic import BaseModel, Field, ConfigDict
from typing import List, Dict, Optional, Literal, Any
from datetime import datetime


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
    suggested_alternative: Optional[Dict[str, str]] = None
    warnings: List[str] = Field(default_factory=list)


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
    issues: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)


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
    location: Optional[str] = None


class AnswerValidationResult(BaseModel):
    """Answer validation result from Answer Validator Agent"""
    is_valid: bool
    overall_score: float = Field(ge=0.0, le=1.0)
    validation_details: AnswerValidationDetails
    issues: List[AnswerIssue] = Field(default_factory=list)
    action: Literal["approve", "flag", "regenerate"]
    execution_time_ms: int
    validation_method: Literal["fast_path", "standard", "deep"]


# ============================================================================
# Quality Orchestration Models
# ============================================================================

class QualityBreakdown(BaseModel):
    """Quality score breakdown by component"""
    route_decision: Dict[str, Any]
    retrieval: Dict[str, Any]
    answer_factuality: Dict[str, Any]
    citations: Dict[str, Any]


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
    user_prompt: Optional[str] = None
    breakdown: QualityBreakdown
    issues: List[Dict[str, str]] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    execution_stats: ExecutionStats


# ============================================================================
# Context Tracking Models
# ============================================================================

class ConversationTurn(BaseModel):
    """Single conversation turn"""
    query: str
    response: str
    route: str
    entities: List[str] = Field(default_factory=list)
    timestamp: datetime


class ConversationContext(BaseModel):
    """Conversation context for session"""
    model_config = ConfigDict(
        json_encoders={
            datetime: lambda v: v.isoformat()
        }
    )

    session_id: str
    user_id: str
    conversation_history: List[ConversationTurn] = Field(default_factory=list, max_length=10)
    topic_stack: List[str] = Field(default_factory=list)
    entity_mentions: Dict[str, int] = Field(default_factory=dict)
    current_intent: Optional[str] = None
    context_summary: Optional[str] = None
    last_update_time: datetime


class ContextHints(BaseModel):
    """Context hints for routing"""
    resolve_references: Optional[Dict[str, int]] = None
    followup: bool = False
    previous_route: Optional[str] = None
    focus_entities: List[str] = Field(default_factory=list)
