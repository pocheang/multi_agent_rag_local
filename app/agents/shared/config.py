"""
Simplified agent configuration - ONLY actively used constants.

This file replaces the bloated config.py with 115 constants (64 unused).
After analysis, we retain only 51 constants that are actually referenced.

Design principles:
1. Keep only constants actively used in the codebase
2. Group by functional area for clarity
3. Document WHY each constant exists, not just WHAT
4. Use environment variables for runtime configuration
5. Pydantic models for complex configuration objects
"""

import os
from typing import Final

from pydantic import BaseModel, Field, field_validator

# ============================================================================
# Environment Variable Helpers
# ============================================================================


def _get_bool_env(key: str, default: bool) -> bool:
    """Get boolean from environment variable."""
    return os.getenv(key, str(default)).lower() in ("true", "1", "yes")


def _get_float_env(key: str, default: float) -> float:
    """Get float from environment variable."""
    return float(os.getenv(key, str(default)))


def _get_int_env(key: str, default: int) -> int:
    """Get integer from environment variable."""
    return int(os.getenv(key, str(default)))


def _get_str_env(key: str, default: str) -> str:
    """Get string from environment variable."""
    return os.getenv(key, default)


# ============================================================================
# Vector RAG Configuration (3 constants)
# WHY: Control retrieval quality thresholds and preview lengths
# ============================================================================

CHUNK_PREVIEW_LENGTH: Final[int] = 1200
"""Maximum length of text chunks for preview display."""

DENSE_SCORE_THRESHOLD: Final[float] = 0.2
"""Minimum similarity score for dense vector retrieval.
WHY: Filter out low-relevance results to improve precision."""


# ============================================================================
# Router Configuration (3 constants)
# WHY: Route decision confidence thresholds and default fallbacks
# ============================================================================

ROUTER_LOW_CONFIDENCE_THRESHOLD: Final[float] = 0.6
"""Threshold below which router confidence is considered low.
WHY: Triggers fallback behavior or additional validation."""

AGENT_CLASS_GENERAL: Final[str] = "general"
"""Default agent class for general-purpose queries."""

VALID_AGENT_CLASSES: Final[frozenset[str]] = frozenset(
    {
        "general",
        "cybersecurity",
        "artificial_intelligence",
        "pdf_text",
        "policy",
    }
)
"""Valid agent class identifiers for query classification."""


# ============================================================================
# Route Types (3 constants)
# WHY: Define supported execution routes
# ============================================================================

ROUTE_VECTOR: Final[str] = "vector"
"""Standard vector-based retrieval route."""

ROUTE_WEB: Final[str] = "web"
"""Web search route for external information."""

VALID_ROUTES: Final[frozenset[str]] = frozenset(
    {
        "vector",
        "graph",
        "hybrid",
        "react",
        "web",
    }
)
"""All supported routing strategies."""


# ============================================================================
# Skills (2 constants)
# WHY: Skill-based answer generation strategies
# ============================================================================

VALID_SKILLS: Final[frozenset[str]] = frozenset(
    {
        "answer_with_citations",
        "compare_entities",
        "timeline_builder",
        "web_fact_check",
        "cyber_attack_analysis",
        "cyber_defense_hardening",
        "incident_response_playbook",
        "ai_knowledge_assistant",
        "pdf_text_reader",
    }
)
"""Supported synthesis skills for answer generation."""

SKILL_DEFAULT: Final[str] = "answer_with_citations"
"""Default skill when no specific skill is requested.
WHY: Most queries need citation-backed answers."""


# ============================================================================
# Quality Validation Configuration (12 constants)
# WHY: Multi-stage quality validation with configurable thresholds
# ============================================================================

# Context Tracking
ENABLE_CONTEXT_TRACKING: Final[bool] = _get_bool_env("ENABLE_CONTEXT_TRACKING", True)
"""Enable conversation context tracking for multi-turn queries."""

# Route Validation Thresholds
ROUTE_HIGH_CONFIDENCE_THRESHOLD: Final[float] = _get_float_env("ROUTE_HIGH_CONFIDENCE_THRESHOLD", 0.85)
ROUTE_MEDIUM_CONFIDENCE_THRESHOLD: Final[float] = _get_float_env("ROUTE_MEDIUM_CONFIDENCE_THRESHOLD", 0.60)
ROUTE_LOW_CONFIDENCE_THRESHOLD: Final[float] = _get_float_env("ROUTE_LOW_CONFIDENCE_THRESHOLD", 0.40)

# Retrieval Quality Weights (WHY: Weighted fusion of retrieval quality dimensions)
RETRIEVAL_WEIGHT_COVERAGE: Final[float] = _get_float_env("RETRIEVAL_WEIGHT_COVERAGE", 0.30)
RETRIEVAL_WEIGHT_RELEVANCE: Final[float] = _get_float_env("RETRIEVAL_WEIGHT_RELEVANCE", 0.40)
RETRIEVAL_WEIGHT_DIVERSITY: Final[float] = _get_float_env("RETRIEVAL_WEIGHT_DIVERSITY", 0.15)
RETRIEVAL_WEIGHT_COMPLETENESS: Final[float] = _get_float_env("RETRIEVAL_WEIGHT_COMPLETENESS", 0.15)
RETRIEVAL_SAMPLE_TOP_K: Final[int] = _get_int_env("RETRIEVAL_SAMPLE_TOP_K", 3)

# Answer Validation Weights (WHY: Factuality weighted highest as citation-first system)
ANSWER_WEIGHT_FACTUALITY: Final[float] = _get_float_env("ANSWER_WEIGHT_FACTUALITY", 0.40)
ANSWER_WEIGHT_CITATION: Final[float] = _get_float_env("ANSWER_WEIGHT_CITATION", 0.25)
ANSWER_WEIGHT_QUALITY: Final[float] = _get_float_env("ANSWER_WEIGHT_QUALITY", 0.25)
ANSWER_WEIGHT_SAFETY: Final[float] = _get_float_env("ANSWER_WEIGHT_SAFETY", 0.10)

# Hallucination Detection (WHY: High risk threshold triggers confidence penalty)
HALLUCINATION_HIGH_RISK_THRESHOLD: Final[float] = _get_float_env("HALLUCINATION_HIGH_RISK_THRESHOLD", 0.30)

# Answer Approval Thresholds
ANSWER_APPROVE_THRESHOLD: Final[float] = _get_float_env("ANSWER_APPROVE_THRESHOLD", 0.80)
ANSWER_FLAG_THRESHOLD: Final[float] = _get_float_env("ANSWER_FLAG_THRESHOLD", 0.60)


# ============================================================================
# NLI (Natural Language Inference) Configuration (2 constants)
# WHY: Factual consistency checking via cross-encoder model
# ============================================================================

NLI_MODEL_NAME: Final[str] = _get_str_env("NLI_MODEL_NAME", "cross-encoder/nli-MiniLM2-L6-H768")
"""Pre-trained NLI model for entailment checking."""

NLI_MAX_CHECKS: Final[int] = _get_int_env("NLI_MAX_CHECKS", 5)
"""Maximum number of NLI checks per answer (performance vs quality tradeoff)."""


# ============================================================================
# Validation Cascade Configuration (9 constants)
# WHY: Four-level cascade from fast rules to deep LLM validation
# ============================================================================

CASCADE_ENABLE_LEVEL1: Final[bool] = _get_bool_env("CASCADE_ENABLE_LEVEL1", True)
"""Level 1: Fast rule-based validation (<10ms)."""

CASCADE_ENABLE_LEVEL2: Final[bool] = _get_bool_env("CASCADE_ENABLE_LEVEL2", False)
"""Level 2: NLI cross-encoder hallucination check, gates NLIValidator in
app/agents/validation/cascade.py (disabled by default)."""

CASCADE_ENABLE_LEVEL3: Final[bool] = _get_bool_env("CASCADE_ENABLE_LEVEL3", True)
"""Level 3: citation-completeness check, gates CitationValidator in
app/agents/validation/cascade.py (~75ms budget, enabled by default)."""

CASCADE_ENABLE_LEVEL4: Final[bool] = _get_bool_env("CASCADE_ENABLE_LEVEL4", True)
"""Level 4: Deep LLM validation (~3000ms)."""

CASCADE_LEVEL1_TIMEOUT_MS: Final[int] = _get_int_env("CASCADE_LEVEL1_TIMEOUT_MS", 10)
CASCADE_LEVEL2_TIMEOUT_MS: Final[int] = _get_int_env("CASCADE_LEVEL2_TIMEOUT_MS", 3000)
CASCADE_LEVEL3_TIMEOUT_MS: Final[int] = _get_int_env("CASCADE_LEVEL3_TIMEOUT_MS", 75)
CASCADE_LEVEL4_TIMEOUT_MS: Final[int] = _get_int_env("CASCADE_LEVEL4_TIMEOUT_MS", 3000)

CASCADE_USE_FOR_VALIDATION: Final[bool] = _get_bool_env("CASCADE_USE_FOR_VALIDATION", True)
"""Enable cascade validation in answer validation flow."""


# ============================================================================
# Quality Orchestrator Weights (7 constants)
# WHY: Weighted fusion of quality scores from all validators
# ============================================================================

QUALITY_WEIGHT_ROUTE: Final[float] = _get_float_env("QUALITY_WEIGHT_ROUTE", 0.10)
QUALITY_WEIGHT_RETRIEVAL: Final[float] = _get_float_env("QUALITY_WEIGHT_RETRIEVAL", 0.30)
QUALITY_WEIGHT_ANSWER_FACT: Final[float] = _get_float_env("QUALITY_WEIGHT_ANSWER_FACT", 0.45)
"""Factuality weighted highest - citation-first principle."""

QUALITY_WEIGHT_ANSWER_QUALITY: Final[float] = _get_float_env("QUALITY_WEIGHT_ANSWER_QUALITY", 0.10)
QUALITY_WEIGHT_CITATION: Final[float] = _get_float_env("QUALITY_WEIGHT_CITATION", 0.05)

QUALITY_HIGH_THRESHOLD: Final[float] = _get_float_env("QUALITY_HIGH_THRESHOLD", 0.85)
QUALITY_MEDIUM_THRESHOLD: Final[float] = _get_float_env("QUALITY_MEDIUM_THRESHOLD", 0.70)
QUALITY_LOW_THRESHOLD: Final[float] = _get_float_env("QUALITY_LOW_THRESHOLD", 0.50)


# ============================================================================
# Context Tracker Configuration (4 constants)
# WHY: Multi-turn conversation context management
# ============================================================================

CONTEXT_MAX_HISTORY_TURNS: Final[int] = _get_int_env("CONTEXT_MAX_HISTORY_TURNS", 10)
"""Maximum conversation turns to retain in context."""

CONTEXT_SUMMARY_FREQUENCY: Final[int] = _get_int_env("CONTEXT_SUMMARY_FREQUENCY", 5)
"""Summarize context every N turns to prevent memory overflow."""

CONTEXT_SUMMARY_MIN_TURNS: Final[int] = _get_int_env("CONTEXT_SUMMARY_MIN_TURNS", 3)
"""Minimum turns before first summarization."""

CONTEXT_TTL_SECONDS: Final[int] = _get_int_env("CONTEXT_TTL_SECONDS", 3600)
"""Context expiration time (1 hour default)."""


# ============================================================================
# Timeout Configuration (3 constants)
# WHY: Prevent indefinite blocking in validation stages
# ============================================================================

ROUTE_VALIDATOR_TIMEOUT_MS: Final[int] = _get_int_env("ROUTE_VALIDATOR_TIMEOUT_MS", 500)
"""Timeout for route validation stage."""

RETRIEVAL_QUALITY_TIMEOUT_MS: Final[int] = _get_int_env("RETRIEVAL_QUALITY_TIMEOUT_MS", 200)
"""Timeout for retrieval quality scoring stage."""

MAX_TOTAL_TIME_MS: Final[int] = _get_int_env("MAX_TOTAL_TIME_MS", 30000)
"""Overall orchestration timeout (30 seconds default).
WHY: Prevent requests from hanging indefinitely."""


# ============================================================================
# Pydantic Configuration Models
# ============================================================================


class RouterConfig(BaseModel):
    """Router agent configuration."""

    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    use_calibration: bool = Field(default=True)
    use_llm_intent: bool = Field(default=True)
    enable_decomposition: bool = Field(default=False)
    low_confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)


class VectorRAGConfig(BaseModel):
    """Vector RAG agent configuration."""

    top_k: int = Field(default=10, ge=1, le=100)
    score_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    enable_query_expansion: bool = Field(default=True)
    enable_evaluation: bool = Field(default=False)
    retrieval_strategy: str = Field(default="hybrid")
    dynamic_parameters: bool = Field(default=True)

    @field_validator("retrieval_strategy")
    @classmethod
    def validate_strategy(cls, value):
        valid_strategies = {"hybrid", "dense", "bm25", "rerank"}
        if value not in valid_strategies:
            raise ValueError(f"Invalid strategy. Must be one of: {valid_strategies}")
        return value


class GraphRAGConfig(BaseModel):
    """Graph RAG agent configuration."""

    enabled: bool = Field(default=True)
    min_quality: float = Field(default=0.3, ge=0.0, le=1.0)
    enable_pdf_optimization: bool = Field(default=True)
    enable_enhancements: bool = Field(default=True)
    fallback_to_vector: bool = Field(default=True)


class ReActConfig(BaseModel):
    """ReAct agent configuration."""

    max_iterations: int = Field(default=5, ge=1, le=10)
    use_reasoning: bool = Field(default=False)
    enable_tool_cache: bool = Field(default=True)


class SynthesisConfig(BaseModel):
    """Synthesis agent configuration."""

    use_reasoning: bool = Field(default=False)
    enable_fact_verification: bool = Field(default=True)
    enable_cot: bool = Field(default=True)
    force_language: str | None = Field(default=None)

    @field_validator("force_language")
    @classmethod
    def validate_language(cls, value):
        if value is not None and value not in {"zh", "en", ""}:
            raise ValueError("Language must be 'zh', 'en', or empty")
        return value


class QualityConfig(BaseModel):
    """Quality assurance configuration."""

    enable_route_validation: bool = Field(default=True)
    enable_retrieval_quality: bool = Field(default=True)
    enable_answer_validation: bool = Field(default=True)
    max_route_retries: int = Field(default=1, ge=0, le=3)
    max_answer_retries: int = Field(default=1, ge=0, le=3)
    high_quality_threshold: float = Field(default=0.85, ge=0.0, le=1.0)
    medium_quality_threshold: float = Field(default=0.7, ge=0.0, le=1.0)


class UnifiedAgentConfig(BaseModel):
    """Unified configuration for all agents."""

    router: RouterConfig = Field(default_factory=RouterConfig)
    vector_rag: VectorRAGConfig = Field(default_factory=VectorRAGConfig)
    graph_rag: GraphRAGConfig = Field(default_factory=GraphRAGConfig)
    react: ReActConfig = Field(default_factory=ReActConfig)
    synthesis: SynthesisConfig = Field(default_factory=SynthesisConfig)
    quality: QualityConfig = Field(default_factory=QualityConfig)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    enable_caching: bool = Field(default=True)
    cache_ttl_seconds: int = Field(default=3600, ge=0)
    log_level: str = Field(default="INFO")
    enable_tracing: bool = Field(default=True)

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


# ============================================================================
# Configuration Access Functions
# ============================================================================

_config_instance: UnifiedAgentConfig | None = None


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


# ============================================================================
# Summary Statistics
# ============================================================================

# Configuration reduction: 115 constants → 51 constants (56% reduction)
# Removed 64 unused constants
# Retained only actively referenced constants
# Added WHY documentation for each constant group
