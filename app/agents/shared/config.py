"""
Component-specific configuration for agents/components.

⚠️ CONFIGURATION DEBT NOTICE ⚠️
This file contains 67+ configuration constants, many of which are legacy
tuning parameters from iterative optimization. This is a known issue.

Roadmap:
- Phase 1: Move shared config to app/core/shared_config.py ✅ (in progress)
- Phase 2: Delete unused constants (target: reduce by 50%)
- Phase 3: Replace hardcoded thresholds with adaptive algorithms

New code should:
1. Avoid adding more constants unless absolutely necessary
2. Consider if behavior should be algorithmic vs. configuration-driven
3. Document WHY a constant exists, not just WHAT it does

Consolidates configuration from:
- shared/config.py (constants)
- shared/unified_config.py (Pydantic models)
- shared/quality_config.py (quality/validation constants)

Design:
- Part 1: Constants (Final types) - for simple thresholds and enums
- Part 2: Pydantic Models - for complex configuration objects
- Part 3: Helper functions - for config access
"""

import os
from typing import Final, Optional

from pydantic import BaseModel, Field, field_validator


# ============================================================================
# PART 1: CONSTANTS
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
# Vector RAG Configuration
# ============================================================================

MAX_CONTEXT_CHUNKS_DEFAULT: Final[int] = 10
CHUNK_PREVIEW_LENGTH: Final[int] = 1200
DENSE_SCORE_THRESHOLD: Final[float] = 0.2
RERANK_SCORE_THRESHOLD: Final[float] = 0.0
BM25_SCORE_THRESHOLD: Final[float] = 0.0
MIN_CHUNK_LENGTH: Final[int] = 10

# ============================================================================
# Router Configuration Constants
# ============================================================================

CLASSIFICATION_HIGH_CONFIDENCE: Final[float] = 0.8
CLASSIFICATION_MEDIUM_CONFIDENCE: Final[float] = 0.6
CLASSIFICATION_LOW_CONFIDENCE: Final[float] = 0.4
ROUTER_LOW_CONFIDENCE_THRESHOLD: Final[float] = 0.6
ROUTER_WEIGHT_KEYWORD: Final[float] = 0.3
ROUTER_WEIGHT_ENTITY_COUNT: Final[float] = 0.2
ROUTER_WEIGHT_QUESTION_TYPE: Final[float] = 0.5
ENTITY_COUNT_HIGH: Final[int] = 3
ENTITY_COUNT_MEDIUM: Final[int] = 2

# ============================================================================
# Synthesis Configuration
# ============================================================================

MAX_ANSWER_LENGTH: Final[int] = 2000
MIN_ANSWER_LENGTH: Final[int] = 50
MIN_CITATIONS_FOR_FACTUAL: Final[int] = 2
MAX_CITATIONS_TO_INCLUDE: Final[int] = 5

# ============================================================================
# Web Research Configuration
# ============================================================================

MAX_WEB_SEARCH_RESULTS: Final[int] = 5
WEB_CONTENT_PREVIEW_LENGTH: Final[int] = 500
WEB_SEARCH_TIMEOUT_MS: Final[int] = 10000
WEB_FETCH_TIMEOUT_MS: Final[int] = 5000

# ============================================================================
# Retrieval Strategy Configuration
# ============================================================================

RETRIEVAL_STRATEGY_HYBRID: Final[str] = "hybrid"
RETRIEVAL_STRATEGY_DENSE: Final[str] = "dense"
RETRIEVAL_STRATEGY_BM25: Final[str] = "bm25"
RETRIEVAL_STRATEGY_RERANK: Final[str] = "rerank"
RETRIEVAL_STRATEGY_DEFAULT: Final[str] = RETRIEVAL_STRATEGY_HYBRID

# ============================================================================
# Agent Classes
# ============================================================================

AGENT_CLASS_GENERAL: Final[str] = "general"
AGENT_CLASS_CYBERSECURITY: Final[str] = "cybersecurity"
AGENT_CLASS_AI: Final[str] = "artificial_intelligence"
AGENT_CLASS_PDF: Final[str] = "pdf_text"
AGENT_CLASS_POLICY: Final[str] = "policy"

VALID_AGENT_CLASSES: Final[frozenset[str]] = frozenset({
    AGENT_CLASS_GENERAL,
    AGENT_CLASS_CYBERSECURITY,
    AGENT_CLASS_AI,
    AGENT_CLASS_PDF,
    AGENT_CLASS_POLICY,
})

# ============================================================================
# Route Types
# ============================================================================

ROUTE_VECTOR: Final[str] = "vector"
ROUTE_GRAPH: Final[str] = "graph"
ROUTE_HYBRID: Final[str] = "hybrid"
ROUTE_REACT: Final[str] = "react"
ROUTE_WEB: Final[str] = "web"

VALID_ROUTES: Final[frozenset[str]] = frozenset({
    ROUTE_VECTOR,
    ROUTE_GRAPH,
    ROUTE_HYBRID,
    ROUTE_REACT,
    ROUTE_WEB,
})

# ============================================================================
# Skills
# ============================================================================

SKILL_ANSWER_WITH_CITATIONS: Final[str] = "answer_with_citations"
SKILL_COMPARE_ENTITIES: Final[str] = "compare_entities"
SKILL_TIMELINE_BUILDER: Final[str] = "timeline_builder"
SKILL_WEB_FACT_CHECK: Final[str] = "web_fact_check"
SKILL_CYBER_ATTACK_ANALYSIS: Final[str] = "cyber_attack_analysis"
SKILL_CYBER_DEFENSE_HARDENING: Final[str] = "cyber_defense_hardening"
SKILL_INCIDENT_RESPONSE_PLAYBOOK: Final[str] = "incident_response_playbook"
SKILL_AI_KNOWLEDGE_ASSISTANT: Final[str] = "ai_knowledge_assistant"
SKILL_PDF_TEXT_READER: Final[str] = "pdf_text_reader"

VALID_SKILLS: Final[frozenset[str]] = frozenset({
    SKILL_ANSWER_WITH_CITATIONS,
    SKILL_COMPARE_ENTITIES,
    SKILL_TIMELINE_BUILDER,
    SKILL_WEB_FACT_CHECK,
    SKILL_CYBER_ATTACK_ANALYSIS,
    SKILL_CYBER_DEFENSE_HARDENING,
    SKILL_INCIDENT_RESPONSE_PLAYBOOK,
    SKILL_AI_KNOWLEDGE_ASSISTANT,
    SKILL_PDF_TEXT_READER,
})

SKILL_DEFAULT: Final[str] = SKILL_ANSWER_WITH_CITATIONS

# ============================================================================
# Quality & Validation Configuration (from quality_config.py)
# ============================================================================

# Global Switches
ENABLE_QUALITY_VALIDATION: Final[bool] = _get_bool_env("ENABLE_QUALITY_VALIDATION", True)
ENABLE_CONTEXT_TRACKING: Final[bool] = _get_bool_env("ENABLE_CONTEXT_TRACKING", True)
ENABLE_VERBOSE_LOGGING: Final[bool] = _get_bool_env("ENABLE_VERBOSE_LOGGING", False)

# Route Validator
ROUTE_HIGH_CONFIDENCE_THRESHOLD: Final[float] = _get_float_env("ROUTE_HIGH_CONFIDENCE_THRESHOLD", 0.85)
ROUTE_MEDIUM_CONFIDENCE_THRESHOLD: Final[float] = _get_float_env("ROUTE_MEDIUM_CONFIDENCE_THRESHOLD", 0.60)
ROUTE_LOW_CONFIDENCE_THRESHOLD: Final[float] = _get_float_env("ROUTE_LOW_CONFIDENCE_THRESHOLD", 0.40)
ROUTE_VALIDATOR_USE_CACHE: Final[bool] = _get_bool_env("ROUTE_VALIDATOR_USE_CACHE", True)
ROUTE_VALIDATOR_CACHE_TTL: Final[int] = _get_int_env("ROUTE_VALIDATOR_CACHE_TTL", 3600)

# Retrieval Quality
RETRIEVAL_WEIGHT_COVERAGE: Final[float] = _get_float_env("RETRIEVAL_WEIGHT_COVERAGE", 0.30)
RETRIEVAL_WEIGHT_RELEVANCE: Final[float] = _get_float_env("RETRIEVAL_WEIGHT_RELEVANCE", 0.40)
RETRIEVAL_WEIGHT_DIVERSITY: Final[float] = _get_float_env("RETRIEVAL_WEIGHT_DIVERSITY", 0.15)
RETRIEVAL_WEIGHT_COMPLETENESS: Final[float] = _get_float_env("RETRIEVAL_WEIGHT_COMPLETENESS", 0.15)
RETRIEVAL_QUALITY_GOOD_THRESHOLD: Final[float] = _get_float_env("RETRIEVAL_QUALITY_GOOD_THRESHOLD", 0.70)
RETRIEVAL_QUALITY_POOR_THRESHOLD: Final[float] = _get_float_env("RETRIEVAL_QUALITY_POOR_THRESHOLD", 0.50)
RETRIEVAL_SAMPLE_TOP_K: Final[int] = _get_int_env("RETRIEVAL_SAMPLE_TOP_K", 3)

# Answer Validator
ANSWER_FAST_PATH_THRESHOLD: Final[float] = _get_float_env("ANSWER_FAST_PATH_THRESHOLD", 0.80)
ANSWER_STANDARD_PATH_THRESHOLD: Final[float] = _get_float_env("ANSWER_STANDARD_PATH_THRESHOLD", 0.60)
ANSWER_WEIGHT_FACTUALITY: Final[float] = _get_float_env("ANSWER_WEIGHT_FACTUALITY", 0.40)
ANSWER_WEIGHT_CITATION: Final[float] = _get_float_env("ANSWER_WEIGHT_CITATION", 0.25)
ANSWER_WEIGHT_QUALITY: Final[float] = _get_float_env("ANSWER_WEIGHT_QUALITY", 0.25)
ANSWER_WEIGHT_SAFETY: Final[float] = _get_float_env("ANSWER_WEIGHT_SAFETY", 0.10)
HALLUCINATION_HIGH_RISK_THRESHOLD: Final[float] = _get_float_env("HALLUCINATION_HIGH_RISK_THRESHOLD", 0.30)
HALLUCINATION_MEDIUM_RISK_THRESHOLD: Final[float] = _get_float_env("HALLUCINATION_MEDIUM_RISK_THRESHOLD", 0.15)
ANSWER_APPROVE_THRESHOLD: Final[float] = _get_float_env("ANSWER_APPROVE_THRESHOLD", 0.80)
ANSWER_FLAG_THRESHOLD: Final[float] = _get_float_env("ANSWER_FLAG_THRESHOLD", 0.60)
NLI_MODEL_NAME: Final[str] = _get_str_env("NLI_MODEL_NAME", "cross-encoder/nli-MiniLM2-L6-H768")
NLI_MAX_CHECKS: Final[int] = _get_int_env("NLI_MAX_CHECKS", 5)

# Validation Cascade
CASCADE_ENABLE_LEVEL1: Final[bool] = _get_bool_env("CASCADE_ENABLE_LEVEL1", True)
CASCADE_ENABLE_LEVEL2: Final[bool] = _get_bool_env("CASCADE_ENABLE_LEVEL2", False)
CASCADE_ENABLE_LEVEL3: Final[bool] = _get_bool_env("CASCADE_ENABLE_LEVEL3", True)
CASCADE_ENABLE_LEVEL4: Final[bool] = _get_bool_env("CASCADE_ENABLE_LEVEL4", True)
CASCADE_LEVEL1_TIMEOUT_MS: Final[int] = _get_int_env("CASCADE_LEVEL1_TIMEOUT_MS", 10)
CASCADE_LEVEL2_TIMEOUT_MS: Final[int] = _get_int_env("CASCADE_LEVEL2_TIMEOUT_MS", 3000)
CASCADE_LEVEL3_TIMEOUT_MS: Final[int] = _get_int_env("CASCADE_LEVEL3_TIMEOUT_MS", 75)
CASCADE_LEVEL4_TIMEOUT_MS: Final[int] = _get_int_env("CASCADE_LEVEL4_TIMEOUT_MS", 3000)
CASCADE_USE_FOR_VALIDATION: Final[bool] = _get_bool_env("CASCADE_USE_FOR_VALIDATION", True)

# Quality Orchestrator
QUALITY_WEIGHT_ROUTE: Final[float] = _get_float_env("QUALITY_WEIGHT_ROUTE", 0.10)
QUALITY_WEIGHT_RETRIEVAL: Final[float] = _get_float_env("QUALITY_WEIGHT_RETRIEVAL", 0.30)
QUALITY_WEIGHT_ANSWER_FACT: Final[float] = _get_float_env("QUALITY_WEIGHT_ANSWER_FACT", 0.45)
QUALITY_WEIGHT_ANSWER_QUALITY: Final[float] = _get_float_env("QUALITY_WEIGHT_ANSWER_QUALITY", 0.10)
QUALITY_WEIGHT_CITATION: Final[float] = _get_float_env("QUALITY_WEIGHT_CITATION", 0.05)
QUALITY_HIGH_THRESHOLD: Final[float] = _get_float_env("QUALITY_HIGH_THRESHOLD", 0.85)
QUALITY_MEDIUM_THRESHOLD: Final[float] = _get_float_env("QUALITY_MEDIUM_THRESHOLD", 0.70)
QUALITY_LOW_THRESHOLD: Final[float] = _get_float_env("QUALITY_LOW_THRESHOLD", 0.50)

# Context Tracker
CONTEXT_MAX_HISTORY_TURNS: Final[int] = _get_int_env("CONTEXT_MAX_HISTORY_TURNS", 10)
CONTEXT_SUMMARY_FREQUENCY: Final[int] = _get_int_env("CONTEXT_SUMMARY_FREQUENCY", 5)
CONTEXT_SUMMARY_MIN_TURNS: Final[int] = _get_int_env("CONTEXT_SUMMARY_MIN_TURNS", 3)
CONTEXT_TTL_SECONDS: Final[int] = _get_int_env("CONTEXT_TTL_SECONDS", 3600)

# Retry Strategy
MAX_ROUTE_RETRIES: Final[int] = _get_int_env("MAX_ROUTE_RETRIES", 1)
MAX_ANSWER_RETRIES: Final[int] = _get_int_env("MAX_ANSWER_RETRIES", 1)
MAX_TOTAL_RETRIES: Final[int] = _get_int_env("MAX_TOTAL_RETRIES", 2)
MAX_TOTAL_TIME_MS: Final[int] = _get_int_env("MAX_TOTAL_TIME_MS", 10000)
ROUTE_VALIDATOR_TIMEOUT_MS: Final[int] = _get_int_env("ROUTE_VALIDATOR_TIMEOUT_MS", 500)
RETRIEVAL_QUALITY_TIMEOUT_MS: Final[int] = _get_int_env("RETRIEVAL_QUALITY_TIMEOUT_MS", 200)
ANSWER_VALIDATOR_TIMEOUT_MS: Final[int] = _get_int_env("ANSWER_VALIDATOR_TIMEOUT_MS", 1000)

# Performance Monitoring
PERF_THRESHOLD_FAST: Final[int] = _get_int_env("PERF_THRESHOLD_FAST", 2000)
PERF_THRESHOLD_MEDIUM: Final[int] = _get_int_env("PERF_THRESHOLD_MEDIUM", 5000)
PERF_THRESHOLD_SLOW: Final[int] = _get_int_env("PERF_THRESHOLD_SLOW", 8000)
ENABLE_PERFORMANCE_LOGGING: Final[bool] = _get_bool_env("ENABLE_PERFORMANCE_LOGGING", True)

# Fallback Configuration
FALLBACK_ROUTE_MAP: Final[dict] = {
    "hybrid": "vector",
    "graph": "vector",
    "react": "vector"
}
ENABLE_AUTO_FALLBACK: Final[bool] = _get_bool_env("ENABLE_AUTO_FALLBACK", True)

# Logging Configuration
LOG_SAMPLE_RATE_HIGH: Final[float] = 1.0
LOG_SAMPLE_RATE_MEDIUM: Final[float] = 0.1
LOG_SAMPLE_RATE_LOW: Final[float] = 0.01


# ============================================================================
# PART 2: PYDANTIC CONFIGURATION MODELS
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
    force_language: Optional[str] = Field(default=None)

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
# PART 3: HELPER FUNCTIONS
# ============================================================================

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
