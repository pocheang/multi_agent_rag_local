"""
Data models for advanced RAG techniques.
"""

from typing import Any

from pydantic import BaseModel, Field, field_validator


class DecomposedQuery(BaseModel):
    """Result of query decomposition."""

    original_query: str = Field(..., description="Original user query")
    sub_queries: list[str] = Field(..., description="List of decomposed sub-queries")
    decomposition_strategy: str = Field(
        ..., description="Strategy used for decomposition: comparison, sequential, parallel, general, or none"
    )

    @field_validator("sub_queries")
    @classmethod
    def validate_sub_queries(cls, v):
        if not v:
            raise ValueError("sub_queries cannot be empty")
        if len(v) > 4:
            raise ValueError("Maximum 4 sub-queries allowed")
        return v

    @field_validator("decomposition_strategy")
    @classmethod
    def validate_strategy(cls, v):
        valid_strategies = ["comparison", "sequential", "parallel", "general", "none"]
        if v not in valid_strategies:
            raise ValueError(f"Strategy must be one of {valid_strategies}")
        return v


class RelevanceScore(BaseModel):
    """Relevance score for a retrieved document."""

    document_id: str = Field(..., description="Document identifier")
    score: float = Field(..., ge=0.0, le=1.0, description="Relevance score (0-1)")
    reasoning: str = Field(..., description="Explanation for the score")


class AnswerQuality(BaseModel):
    """Quality evaluation of a generated answer."""

    score: float = Field(..., ge=0.0, le=1.0, description="Overall quality score (0-1)")
    completeness: float = Field(..., ge=0.0, le=1.0, description="Completeness score (0-1)")
    accuracy: float = Field(..., ge=0.0, le=1.0, description="Accuracy score (0-1)")
    relevance: float = Field(..., ge=0.0, le=1.0, description="Relevance score (0-1)")
    feedback: str = Field(..., description="Detailed feedback on answer quality")
    needs_refinement: bool = Field(..., description="Whether answer needs refinement")


class SubQueryResult(BaseModel):
    """Result from processing a single sub-query."""

    sub_query: str = Field(..., description="The sub-query that was processed")
    documents: list[dict[str, Any]] = Field(..., description="Retrieved documents")
    answer: str = Field(..., description="Generated answer for this sub-query")
    relevance_scores: list[RelevanceScore] | None = Field(
        None, description="Relevance scores for documents (if Self-RAG enabled)"
    )


class AdvancedRAGResult(BaseModel):
    """Complete result from advanced RAG processing."""

    query: str = Field(..., description="Original user query")
    decomposed_query: DecomposedQuery | None = Field(None, description="Decomposed query (if decomposition was used)")
    sub_query_results: list[SubQueryResult] = Field(..., description="Results from each sub-query")
    final_answer: str = Field(..., description="Final synthesized answer")
    answer_quality: AnswerQuality | None = Field(
        None, description="Quality evaluation of final answer (if Self-RAG enabled)"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata (latency, token usage, etc.)"
    )
