"""Canonical result schemas shared by compatibility agent entry points."""

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


class AgentResult(BaseModel):
    status: Literal["success", "failed", "partial"] = Field(..., description="Execution status")
    agent_name: str = Field(..., description="Name of the agent that produced this result")
    answer: Optional[str] = Field(None, description="Generated answer (if applicable)")
    context: Optional[str] = Field(None, description="Retrieved or generated context")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata specific to the agent")
    citations: List[Dict[str, Any]] = Field(default_factory=list, description="Source citations with metadata")
    execution_time_ms: Optional[float] = Field(None, description="Execution time in milliseconds")
    timestamp: Optional[float] = Field(None, description="Unix timestamp of execution")
    error: Optional[str] = Field(None, description="Error message if execution failed")
    error_type: Optional[str] = Field(None, description="Type of error that occurred")

    class Config:
        extra = "allow"


class RouterResult(AgentResult):
    route: str = Field(..., description="Selected route: vector, graph, hybrid, react, web")
    reason: str = Field(..., description="Reasoning for the route decision")
    skill: str = Field(..., description="Selected skill for execution")
    agent_class: str = Field(..., description="Classified agent class")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score for the routing decision")
    decomposed_query: Optional[Dict[str, Any]] = Field(None, description="Decomposed query structure if applicable")
    route_decisions: List[Dict[str, Any]] = Field(default_factory=list, description="Route decisions for sub-queries if decomposed")


class VectorRAGResult(AgentResult):
    retrieved_count: int = Field(0, ge=0, description="Total number of chunks retrieved")
    effective_hit_count: int = Field(0, ge=0, description="Number of high-quality/relevant chunks")
    retrieval_diagnostics: Dict[str, Any] = Field(default_factory=dict, description="Diagnostic information about retrieval process")
    original_query: Optional[str] = Field(None, description="Original query before expansion")
    expanded_query: Optional[str] = Field(None, description="Expanded query with synonyms")
    retrieval_strategy: Optional[str] = Field(None, description="Retrieval strategy used: hybrid, dense, bm25, rerank")


class GraphRAGResult(AgentResult):
    entities: List[str] = Field(default_factory=list, description="Matched entity names")
    neighbors: List[Dict[str, Any]] = Field(default_factory=list, description="Neighbor relationships")
    paths: List[Dict[str, Any]] = Field(default_factory=list, description="Multi-hop paths between entities")
    relationships: List[Dict[str, Any]] = Field(default_factory=list, description="Direct relationships")
    graph_signal_score: float = Field(0.0, ge=0.0, le=1.0, description="Graph relevance score")
    confidence: Optional[str] = Field(None, description="Confidence level: high, medium, low")
    pdf_context: Optional[Dict[str, Any]] = Field(None, description="PDF context analysis if applicable")
    fallback_used: bool = Field(False, description="Whether fallback to vector RAG was used")
    fallback_reason: Optional[str] = Field(None, description="Reason for fallback if applicable")


class ReActResult(AgentResult):
    react_history: List[Dict[str, Any]] = Field(default_factory=list, description="History of thought-action-observation cycles")
    iterations_used: int = Field(0, ge=0, description="Number of iterations used")
    max_iterations: int = Field(5, ge=1, description="Maximum iterations allowed")
    contexts: Dict[str, str] = Field(default_factory=dict, description="Contexts from vector, graph, web searches")
    vector_result: Dict[str, Any] = Field(default_factory=dict, description="Vector search results")
    graph_result: Dict[str, Any] = Field(default_factory=dict, description="Graph query results")
    web_result: Dict[str, Any] = Field(default_factory=dict, description="Web search results")


class SynthesisResult(AgentResult):
    detected_language: str = Field("zh", description="Detected output language")
    skill_used: str = Field(..., description="Skill used for synthesis")
    reasoning_used: bool = Field(False, description="Whether reasoning model was used")
    vector_context: Optional[str] = Field(None, description="Vector RAG context")
    graph_context: Optional[str] = Field(None, description="Graph RAG context")
    web_context: Optional[str] = Field(None, description="Web search context")
    fact_verification: Optional[Dict[str, Any]] = Field(None, description="Fact verification results")


class QualityReport(BaseModel):
    quality_level: Literal["high", "medium", "low", "very_low"] = Field(..., description="Overall quality classification")
    overall_score: float = Field(..., ge=0.0, le=1.0, description="Overall quality score")
    route_confidence: float = Field(..., ge=0.0, le=1.0, description="Routing confidence")
    retrieval_quality: float = Field(..., ge=0.0, le=1.0, description="Retrieval quality score")
    answer_quality: float = Field(..., ge=0.0, le=1.0, description="Answer quality score")
    route_validated: bool = Field(False, description="Whether route was validated")
    retrieval_validated: bool = Field(False, description="Whether retrieval was validated")
    answer_validated: bool = Field(False, description="Whether answer was validated")
    issues: List[str] = Field(default_factory=list, description="Identified quality issues")
    recommendations: List[str] = Field(default_factory=list, description="Improvement recommendations")


class EnhancedRAGResult(AgentResult):
    route_used: str = Field(..., description="Route that was used")
    route_reason: str = Field(..., description="Reason for route selection")
    skill_used: str = Field(..., description="Skill that was used")
    agent_class: str = Field(..., description="Agent class")
    quality_report: QualityReport = Field(..., description="Comprehensive quality assessment")
    execution_metadata: Dict[str, Any] = Field(default_factory=dict, description="Execution performance metrics")


RouterDecision = RouterResult
VectorRAGResponse = VectorRAGResult
GraphRAGResponse = GraphRAGResult


def result_to_dict(result: AgentResult) -> Dict[str, Any]:
    return result.model_dump(exclude_none=True)


def dict_to_result(data: Dict[str, Any], result_class: type = AgentResult) -> AgentResult:
    return result_class(**data)


__all__ = [
    "AgentResult", "RouterResult", "VectorRAGResult", "GraphRAGResult", "ReActResult",
    "SynthesisResult", "QualityReport", "EnhancedRAGResult", "RouterDecision",
    "VectorRAGResponse", "GraphRAGResponse", "result_to_dict", "dict_to_result",
]
