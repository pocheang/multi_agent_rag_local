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

from typing import Final

from pydantic import BaseModel, Field, field_validator

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

# Route Validation Thresholds

# Retrieval Quality Weights (WHY: Weighted fusion of retrieval quality dimensions)

# Answer Validation Weights (WHY: Factuality weighted highest as citation-first system)
ANSWER_WEIGHT_FACTUALITY: Final[float] = 0.40
ANSWER_WEIGHT_CITATION: Final[float] = 0.25
ANSWER_WEIGHT_QUALITY: Final[float] = 0.25
ANSWER_WEIGHT_SAFETY: Final[float] = 0.10

# Hallucination Detection (WHY: High risk threshold triggers confidence penalty)

# Answer Approval Thresholds


# ============================================================================
# NLI (Natural Language Inference) Configuration (2 constants)
# WHY: Factual consistency checking via cross-encoder model
# ============================================================================


# ============================================================================
# Validation Cascade Configuration (9 constants)
# WHY: Four-level cascade from fast rules to deep LLM validation
# ============================================================================


# ============================================================================
# Quality Orchestrator Weights (7 constants)
# WHY: Weighted fusion of quality scores from all validators
# ============================================================================


"""Summarize context every N turns to prevent memory overflow."""

"""Minimum turns before first summarization."""

"""Context expiration time (1 hour default)."""


# ============================================================================
# Timeout Configuration (3 constants)
# WHY: Prevent indefinite blocking in validation stages
# ============================================================================


# ============================================================================
# Pydantic Configuration Models
# ============================================================================


class VectorRAGConfig(BaseModel):
    """Vector RAG agent configuration."""

    top_k: int = Field(default=10, ge=1, le=100)
    score_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    enable_query_expansion: bool = Field(default=True)
    retrieval_strategy: str = Field(default="hybrid")
    dynamic_parameters: bool = Field(default=True)

    @field_validator("retrieval_strategy")
    @classmethod
    def validate_strategy(cls, value):
        valid_strategies = {"hybrid", "dense", "bm25", "rerank"}
        if value not in valid_strategies:
            raise ValueError(f"Invalid strategy. Must be one of: {valid_strategies}")
        return value


class UnifiedAgentConfig(BaseModel):
    """Unified configuration for all agents.

    Five sibling sections -- router, graph_rag, react, synthesis, quality -- were
    deleted on 2026-09-06 with the accessors that were their only readers. They
    were worse than unused: their defaults contradicted the running system
    (`SynthesisConfig.enable_fact_verification` read True beside a synthesizer
    that passes False, and `RouterConfig.use_calibration` True beside an
    `ENABLE_CALIBRATION` that defaults False), so anyone reading this file for
    the configuration found the opposite of what runs.

    `vector_rag` is the one section with a live reader, `app/agents/rag/vector.py`.
    """

    vector_rag: VectorRAGConfig = Field(default_factory=VectorRAGConfig)
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


def get_vector_rag_config() -> VectorRAGConfig:
    """Get vector RAG configuration."""
    return get_agent_config().vector_rag


# ============================================================================
# Summary Statistics
# ============================================================================

# Configuration reduction: 115 constants → 51 constants (56% reduction)
# Removed 64 unused constants
# Retained only actively referenced constants
# Added WHY documentation for each constant group
