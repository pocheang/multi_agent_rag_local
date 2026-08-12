"""
Configuration constants for all RAG agents.

Centralizes thresholds, limits, and scoring parameters
to eliminate magic numbers and improve maintainability.
"""

from typing import Final

# ============================================================================
# Vector RAG Configuration
# ============================================================================

# Context chunk limits
MAX_CONTEXT_CHUNKS_DEFAULT: Final[int] = 10
CHUNK_PREVIEW_LENGTH: Final[int] = 1200

# Score thresholds for evidence gating
DENSE_SCORE_THRESHOLD: Final[float] = 0.2
RERANK_SCORE_THRESHOLD: Final[float] = 0.0
BM25_SCORE_THRESHOLD: Final[float] = 0.0

# Effective hit counting
MIN_CHUNK_LENGTH: Final[int] = 10  # Minimum text length to count as valid

# ============================================================================
# Router Configuration
# ============================================================================

# Agent classification confidence thresholds
CLASSIFICATION_HIGH_CONFIDENCE: Final[float] = 0.8
CLASSIFICATION_MEDIUM_CONFIDENCE: Final[float] = 0.6
CLASSIFICATION_LOW_CONFIDENCE: Final[float] = 0.4

# Router fallback threshold
# If route confidence < this threshold, trigger fallback strategy
ROUTER_LOW_CONFIDENCE_THRESHOLD: Final[float] = 0.6

# Router decision weights
ROUTER_WEIGHT_KEYWORD: Final[float] = 0.3
ROUTER_WEIGHT_ENTITY_COUNT: Final[float] = 0.2
ROUTER_WEIGHT_QUESTION_TYPE: Final[float] = 0.5

# Entity count thresholds for routing
ENTITY_COUNT_HIGH: Final[int] = 3
ENTITY_COUNT_MEDIUM: Final[int] = 2

# ============================================================================
# Synthesis Configuration
# ============================================================================

# Answer generation limits
MAX_ANSWER_LENGTH: Final[int] = 2000
MIN_ANSWER_LENGTH: Final[int] = 50

# Citation requirements
MIN_CITATIONS_FOR_FACTUAL: Final[int] = 2
MAX_CITATIONS_TO_INCLUDE: Final[int] = 5

# ============================================================================
# Web Research Configuration
# ============================================================================

# Web search limits
MAX_WEB_SEARCH_RESULTS: Final[int] = 5
WEB_CONTENT_PREVIEW_LENGTH: Final[int] = 500

# Timeout settings (milliseconds)
WEB_SEARCH_TIMEOUT_MS: Final[int] = 10000
WEB_FETCH_TIMEOUT_MS: Final[int] = 5000

# ============================================================================
# Retrieval Strategy Configuration
# ============================================================================

# Available strategies
RETRIEVAL_STRATEGY_HYBRID: Final[str] = "hybrid"
RETRIEVAL_STRATEGY_DENSE: Final[str] = "dense"
RETRIEVAL_STRATEGY_BM25: Final[str] = "bm25"
RETRIEVAL_STRATEGY_RERANK: Final[str] = "rerank"

# Default strategy
RETRIEVAL_STRATEGY_DEFAULT: Final[str] = RETRIEVAL_STRATEGY_HYBRID

# ============================================================================
# Agent Classes
# ============================================================================

AGENT_CLASS_GENERAL: Final[str] = "general"
AGENT_CLASS_CYBERSECURITY: Final[str] = "cybersecurity"
AGENT_CLASS_AI: Final[str] = "artificial_intelligence"
AGENT_CLASS_PDF: Final[str] = "pdf_text"
AGENT_CLASS_POLICY: Final[str] = "policy"

VALID_AGENT_CLASSES: Final[frozenset[str]] = frozenset(
    {
        AGENT_CLASS_GENERAL,
        AGENT_CLASS_CYBERSECURITY,
        AGENT_CLASS_AI,
        AGENT_CLASS_PDF,
        AGENT_CLASS_POLICY,
    }
)

# ============================================================================
# Route Types
# ============================================================================

ROUTE_VECTOR: Final[str] = "vector"
ROUTE_GRAPH: Final[str] = "graph"
ROUTE_HYBRID: Final[str] = "hybrid"
ROUTE_REACT: Final[str] = "react"
ROUTE_WEB: Final[str] = "web"

VALID_ROUTES: Final[frozenset[str]] = frozenset(
    {
        ROUTE_VECTOR,
        ROUTE_GRAPH,
        ROUTE_HYBRID,
        ROUTE_REACT,
        ROUTE_WEB,
    }
)

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

VALID_SKILLS: Final[frozenset[str]] = frozenset(
    {
        SKILL_ANSWER_WITH_CITATIONS,
        SKILL_COMPARE_ENTITIES,
        SKILL_TIMELINE_BUILDER,
        SKILL_WEB_FACT_CHECK,
        SKILL_CYBER_ATTACK_ANALYSIS,
        SKILL_CYBER_DEFENSE_HARDENING,
        SKILL_INCIDENT_RESPONSE_PLAYBOOK,
        SKILL_AI_KNOWLEDGE_ASSISTANT,
        SKILL_PDF_TEXT_READER,
    }
)

# Default skill
SKILL_DEFAULT: Final[str] = SKILL_ANSWER_WITH_CITATIONS

# ============================================================================
# Logging and Monitoring
# ============================================================================

# Log sampling rates
LOG_SAMPLE_RATE_HIGH: Final[float] = 1.0  # 100%
LOG_SAMPLE_RATE_MEDIUM: Final[float] = 0.1  # 10%
LOG_SAMPLE_RATE_LOW: Final[float] = 0.01  # 1%

# Performance thresholds (milliseconds)
PERF_THRESHOLD_SLOW: Final[int] = 5000
PERF_THRESHOLD_MEDIUM: Final[int] = 2000
PERF_THRESHOLD_FAST: Final[int] = 1000
