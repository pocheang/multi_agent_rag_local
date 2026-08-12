"""Historical public result-schema imports; canonical owner is ``agents.shared``."""

from app.agents.shared.result_schemas import (
    AgentResult,
    EnhancedRAGResult,
    GraphRAGResponse,
    GraphRAGResult,
    QualityReport,
    ReActResult,
    RouterDecision,
    RouterResult,
    SynthesisResult,
    VectorRAGResponse,
    VectorRAGResult,
    dict_to_result,
    result_to_dict,
)

__all__ = [
    "AgentResult", "RouterResult", "VectorRAGResult", "GraphRAGResult", "ReActResult",
    "SynthesisResult", "QualityReport", "EnhancedRAGResult", "RouterDecision",
    "VectorRAGResponse", "GraphRAGResponse", "result_to_dict", "dict_to_result",
]
