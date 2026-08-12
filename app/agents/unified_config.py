"""Compatibility re-export for app.agents.shared.unified_config; implementation lives in the canonical package."""

from app.agents.shared.unified_config import (
    GraphRAGConfig,
    QualityConfig,
    ReActConfig,
    RouterConfig,
    SynthesisConfig,
    UnifiedAgentConfig,
    VectorRAGConfig,
    get_agent_config,
    get_graph_rag_config,
    get_quality_config,
    get_react_config,
    get_router_config,
    get_synthesis_config,
    get_vector_rag_config,
    reset_agent_config,
    set_agent_config,
)

__all__ = [
    "RouterConfig",
    "VectorRAGConfig",
    "GraphRAGConfig",
    "ReActConfig",
    "SynthesisConfig",
    "QualityConfig",
    "UnifiedAgentConfig",
    "get_agent_config",
    "set_agent_config",
    "reset_agent_config",
    "get_router_config",
    "get_vector_rag_config",
    "get_graph_rag_config",
    "get_react_config",
    "get_synthesis_config",
    "get_quality_config",
]
