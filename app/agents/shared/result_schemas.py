"""Canonical result schemas shared by compatibility agent entry points."""

from typing import Any, Literal

from pydantic import BaseModel, Field


class AgentResult(BaseModel):
    status: Literal["success", "failed", "partial"] = Field(..., description="Execution status")
    agent_name: str = Field(..., description="Name of the agent that produced this result")
    answer: str | None = Field(None, description="Generated answer (if applicable)")
    context: str | None = Field(None, description="Retrieved or generated context")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata specific to the agent")
    citations: list[dict[str, Any]] = Field(default_factory=list, description="Source citations with metadata")
    execution_time_ms: float | None = Field(None, description="Execution time in milliseconds")
    timestamp: float | None = Field(None, description="Unix timestamp of execution")
    error: str | None = Field(None, description="Error message if execution failed")
    error_type: str | None = Field(None, description="Type of error that occurred")

    class Config:
        extra = "allow"


class RouterResult(AgentResult):
    route: str = Field(..., description="Selected route: vector, graph, hybrid, react, web")
    reason: str = Field(..., description="Reasoning for the route decision")
    skill: str = Field(..., description="Selected skill for execution")
    agent_class: str = Field(..., description="Classified agent class")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score for the routing decision")
    decomposed_query: dict[str, Any] | None = Field(None, description="Decomposed query structure if applicable")
    route_decisions: list[dict[str, Any]] = Field(
        default_factory=list, description="Route decisions for sub-queries if decomposed"
    )


class VectorRAGResult(AgentResult):
    retrieved_count: int = Field(0, ge=0, description="Total number of chunks retrieved")
    effective_hit_count: int = Field(0, ge=0, description="Number of high-quality/relevant chunks")
    retrieval_diagnostics: dict[str, Any] = Field(
        default_factory=dict, description="Diagnostic information about retrieval process"
    )
    original_query: str | None = Field(None, description="Original query before expansion")
    expanded_query: str | None = Field(None, description="Expanded query with synonyms")
    retrieval_strategy: str | None = Field(None, description="Retrieval strategy used: hybrid, dense, bm25, rerank")


class GraphRAGResult(AgentResult):
    entities: list[str] = Field(default_factory=list, description="Matched entity names")
    neighbors: list[dict[str, Any]] = Field(default_factory=list, description="Neighbor relationships")
    paths: list[dict[str, Any]] = Field(default_factory=list, description="Multi-hop paths between entities")
    relationships: list[dict[str, Any]] = Field(default_factory=list, description="Direct relationships")
    graph_signal_score: float = Field(0.0, ge=0.0, le=1.0, description="Graph relevance score")
    confidence: str | None = Field(None, description="Confidence level: high, medium, low")
    pdf_context: dict[str, Any] | None = Field(None, description="PDF context analysis if applicable")
    fallback_used: bool = Field(False, description="Whether fallback to vector RAG was used")
    fallback_reason: str | None = Field(None, description="Reason for fallback if applicable")


class ReActResult(AgentResult):
    react_history: list[dict[str, Any]] = Field(
        default_factory=list, description="History of thought-action-observation cycles"
    )
    iterations_used: int = Field(0, ge=0, description="Number of iterations used")
    max_iterations: int = Field(5, ge=1, description="Maximum iterations allowed")
    contexts: dict[str, str] = Field(default_factory=dict, description="Contexts from vector, graph, web searches")
    vector_result: dict[str, Any] = Field(default_factory=dict, description="Vector search results")
    graph_result: dict[str, Any] = Field(default_factory=dict, description="Graph query results")
    web_result: dict[str, Any] = Field(default_factory=dict, description="Web search results")


class SynthesisResult(AgentResult):
    detected_language: str = Field("zh", description="Detected output language")
    skill_used: str = Field(..., description="Skill used for synthesis")
    reasoning_used: bool = Field(False, description="Whether reasoning model was used")
    vector_context: str | None = Field(None, description="Vector RAG context")
    graph_context: str | None = Field(None, description="Graph RAG context")
    web_context: str | None = Field(None, description="Web search context")
    fact_verification: dict[str, Any] | None = Field(None, description="Fact verification results")


# Legacy QualityReport and EnhancedRAGResult removed - unused schemas
# Active quality reporting uses:
#   - app.agents.shared.quality_models.QualityReport (quality_orchestrator)
#   - app.domain.contracts.OrchestratedQualityReport (finalization)


RouterDecision = RouterResult
VectorRAGResponse = VectorRAGResult
GraphRAGResponse = GraphRAGResult


def result_to_dict(result: AgentResult) -> dict[str, Any]:
    return result.model_dump(exclude_none=True)


def dict_to_result(data: dict[str, Any], result_class: type = AgentResult) -> AgentResult:
    return result_class(**data)


__all__ = [
    "AgentResult",
    "RouterResult",
    "VectorRAGResult",
    "GraphRAGResult",
    "ReActResult",
    "SynthesisResult",
    "RouterDecision",
    "VectorRAGResponse",
    "GraphRAGResponse",
    "result_to_dict",
    "dict_to_result",
]
