"""Unified shared configuration for canonical Agent implementations."""

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class RouterConfig(BaseModel):
    """Router agent configuration."""

    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum confidence threshold for routing decisions")
    use_calibration: bool = Field(default=True, description="Enable confidence calibration")
    use_llm_intent: bool = Field(default=True, description="Use LLM for intent classification")
    enable_decomposition: bool = Field(default=False, description="Enable query decomposition for complex queries")
    low_confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0, description="Threshold for triggering fallback with reasoning model")


class VectorRAGConfig(BaseModel):
    """Vector RAG agent configuration."""

    top_k: int = Field(default=10, ge=1, le=100, description="Number of chunks to retrieve")
    score_threshold: float = Field(default=0.5, ge=0.0, le=1.0, description="Minimum similarity score threshold")
    enable_query_expansion: bool = Field(default=True, description="Enable query expansion with synonyms")
    enable_evaluation: bool = Field(default=False, description="Enable retrieval quality evaluation")
    retrieval_strategy: str = Field(default="hybrid", description="Retrieval strategy: hybrid, dense, bm25, rerank")
    dynamic_parameters: bool = Field(default=True, description="Enable dynamic parameter tuning based on query complexity")

    @field_validator("retrieval_strategy")
    @classmethod
    def validate_strategy(cls, value):
        valid_strategies = {"hybrid", "dense", "bm25", "rerank"}
        if value not in valid_strategies:
            raise ValueError(f"Invalid strategy. Must be one of: {valid_strategies}")
        return value


class GraphRAGConfig(BaseModel):
    """Graph RAG agent configuration."""

    enabled: bool = Field(default=True, description="Enable graph RAG")
    min_quality: float = Field(default=0.3, ge=0.0, le=1.0, description="Minimum PDF quality threshold for graph queries")
    enable_pdf_optimization: bool = Field(default=True, description="Enable PDF-aware optimization")
    enable_enhancements: bool = Field(default=True, description="Enable enhanced features")
    fallback_to_vector: bool = Field(default=True, description="Fallback to vector RAG on errors")


class ReActConfig(BaseModel):
    """ReAct agent configuration."""

    max_iterations: int = Field(default=5, ge=1, le=10, description="Maximum reasoning iterations")
    use_reasoning: bool = Field(default=False, description="Use reasoning model for better quality")
    enable_tool_cache: bool = Field(default=True, description="Cache tool results within session")


class SynthesisConfig(BaseModel):
    """Synthesis agent configuration."""

    use_reasoning: bool = Field(default=False, description="Use reasoning model for synthesis")
    enable_fact_verification: bool = Field(default=True, description="Enable fact verification")
    enable_cot: bool = Field(default=True, description="Enable chain-of-thought reasoning")
    force_language: Optional[str] = Field(default=None, description="Force output language (zh/en)")

    @field_validator("force_language")
    @classmethod
    def validate_language(cls, value):
        if value is not None and value not in {"zh", "en", ""}:
            raise ValueError("Language must be 'zh', 'en', or empty")
        return value


class QualityConfig(BaseModel):
    """Quality assurance configuration."""

    enable_route_validation: bool = Field(default=True, description="Enable route validation")
    enable_retrieval_quality: bool = Field(default=True, description="Enable retrieval quality assessment")
    enable_answer_validation: bool = Field(default=True, description="Enable answer validation")
    max_route_retries: int = Field(default=1, ge=0, le=3, description="Maximum route retries on low confidence")
    max_answer_retries: int = Field(default=1, ge=0, le=3, description="Maximum answer retries on validation failure")
    high_quality_threshold: float = Field(default=0.85, ge=0.0, le=1.0, description="Threshold for high quality classification")
    medium_quality_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Threshold for medium quality classification")


class UnifiedAgentConfig(BaseModel):
    """Unified configuration for all agents."""

    router: RouterConfig = Field(default_factory=RouterConfig)
    vector_rag: VectorRAGConfig = Field(default_factory=VectorRAGConfig)
    graph_rag: GraphRAGConfig = Field(default_factory=GraphRAGConfig)
    react: ReActConfig = Field(default_factory=ReActConfig)
    synthesis: SynthesisConfig = Field(default_factory=SynthesisConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    timeout_seconds: int = Field(default=30, ge=1, le=300, description="Global timeout for agent execution")
    enable_caching: bool = Field(default=True, description="Enable result caching")
    cache_ttl_seconds: int = Field(default=3600, ge=0, description="Cache time-to-live in seconds")
    log_level: str = Field(default="INFO", description="Logging level")
    enable_tracing: bool = Field(default=True, description="Enable execution tracing")

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, value):
        valid_levels = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
        if value.upper() not in valid_levels:
            raise ValueError(f"Invalid log level. Must be one of: {valid_levels}")
        return value.upper()

    class Config:
        """Pydantic config."""

        validate_assignment = True
        extra = "forbid"


_config_instance: Optional[UnifiedAgentConfig] = None


def get_agent_config() -> UnifiedAgentConfig:
    """Get the global agent configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = UnifiedAgentConfig()
    return _config_instance


def set_agent_config(config: UnifiedAgentConfig):
    """Set the global agent configuration."""
    global _config_instance
    _config_instance = config


def reset_agent_config():
    """Reset configuration to defaults."""
    global _config_instance
    _config_instance = UnifiedAgentConfig()


def get_router_config() -> RouterConfig:
    """Get router configuration."""
    return get_agent_config().router


def get_vector_rag_config() -> VectorRAGConfig:
    """Get vector RAG configuration."""
    return get_agent_config().vector_rag


def get_graph_rag_config() -> GraphRAGConfig:
    """Get graph RAG configuration."""
    return get_agent_config().graph_rag


def get_react_config() -> ReActConfig:
    """Get ReAct configuration."""
    return get_agent_config().react


def get_synthesis_config() -> SynthesisConfig:
    """Get synthesis configuration."""
    return get_agent_config().synthesis


def get_quality_config() -> QualityConfig:
    """Get quality configuration."""
    return get_agent_config().quality
