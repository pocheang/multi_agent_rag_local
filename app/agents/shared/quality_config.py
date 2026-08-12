"""
Configuration constants for quality assurance system.

Supports environment variable overrides for production deployment.
Set environment variables with the same name to override defaults.

Example:
    export ENABLE_QUALITY_VALIDATION=false
    export ROUTE_HIGH_CONFIDENCE_THRESHOLD=0.90
    export NLI_MODEL_NAME=cross-encoder/nli-deberta-base
"""

import os
from typing import Final


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
# Global Switches
# ============================================================================

ENABLE_QUALITY_VALIDATION: Final[bool] = _get_bool_env("ENABLE_QUALITY_VALIDATION", True)
ENABLE_CONTEXT_TRACKING: Final[bool] = _get_bool_env("ENABLE_CONTEXT_TRACKING", True)
ENABLE_VERBOSE_LOGGING: Final[bool] = _get_bool_env("ENABLE_VERBOSE_LOGGING", False)


# ============================================================================
# Route Validator Configuration
# ============================================================================

ROUTE_HIGH_CONFIDENCE_THRESHOLD: Final[float] = _get_float_env("ROUTE_HIGH_CONFIDENCE_THRESHOLD", 0.85)
ROUTE_MEDIUM_CONFIDENCE_THRESHOLD: Final[float] = _get_float_env("ROUTE_MEDIUM_CONFIDENCE_THRESHOLD", 0.60)
ROUTE_LOW_CONFIDENCE_THRESHOLD: Final[float] = _get_float_env("ROUTE_LOW_CONFIDENCE_THRESHOLD", 0.40)
ROUTE_VALIDATOR_USE_CACHE: Final[bool] = _get_bool_env("ROUTE_VALIDATOR_USE_CACHE", True)
ROUTE_VALIDATOR_CACHE_TTL: Final[int] = _get_int_env("ROUTE_VALIDATOR_CACHE_TTL", 3600)


# ============================================================================
# Retrieval Quality Configuration
# ============================================================================

RETRIEVAL_WEIGHT_COVERAGE: Final[float] = _get_float_env("RETRIEVAL_WEIGHT_COVERAGE", 0.30)
RETRIEVAL_WEIGHT_RELEVANCE: Final[float] = _get_float_env("RETRIEVAL_WEIGHT_RELEVANCE", 0.40)
RETRIEVAL_WEIGHT_DIVERSITY: Final[float] = _get_float_env("RETRIEVAL_WEIGHT_DIVERSITY", 0.15)
RETRIEVAL_WEIGHT_COMPLETENESS: Final[float] = _get_float_env("RETRIEVAL_WEIGHT_COMPLETENESS", 0.15)
RETRIEVAL_QUALITY_GOOD_THRESHOLD: Final[float] = _get_float_env("RETRIEVAL_QUALITY_GOOD_THRESHOLD", 0.70)
RETRIEVAL_QUALITY_POOR_THRESHOLD: Final[float] = _get_float_env("RETRIEVAL_QUALITY_POOR_THRESHOLD", 0.50)
RETRIEVAL_SAMPLE_TOP_K: Final[int] = _get_int_env("RETRIEVAL_SAMPLE_TOP_K", 3)


# ============================================================================
# Answer Validator Configuration
# ============================================================================

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

# Validation Cascade Configuration (Task 8)
CASCADE_ENABLE_LEVEL1: Final[bool] = _get_bool_env("CASCADE_ENABLE_LEVEL1", True)
# Level 2 disabled by default due to 2-3s performance overhead (1900% over 100ms target)
# Enable with CASCADE_ENABLE_LEVEL2=true for higher accuracy at cost of latency
CASCADE_ENABLE_LEVEL2: Final[bool] = _get_bool_env("CASCADE_ENABLE_LEVEL2", False)
CASCADE_ENABLE_LEVEL3: Final[bool] = _get_bool_env("CASCADE_ENABLE_LEVEL3", True)
CASCADE_ENABLE_LEVEL4: Final[bool] = _get_bool_env("CASCADE_ENABLE_LEVEL4", True)
CASCADE_LEVEL1_TIMEOUT_MS: Final[int] = _get_int_env("CASCADE_LEVEL1_TIMEOUT_MS", 10)
CASCADE_LEVEL2_TIMEOUT_MS: Final[int] = _get_int_env("CASCADE_LEVEL2_TIMEOUT_MS", 3000)  # Realistic: 2-3s
CASCADE_LEVEL3_TIMEOUT_MS: Final[int] = _get_int_env("CASCADE_LEVEL3_TIMEOUT_MS", 75)
CASCADE_LEVEL4_TIMEOUT_MS: Final[int] = _get_int_env("CASCADE_LEVEL4_TIMEOUT_MS", 3000)  # Realistic for LLM
CASCADE_USE_FOR_VALIDATION: Final[bool] = _get_bool_env("CASCADE_USE_FOR_VALIDATION", True)


# ============================================================================
# Quality Orchestrator Configuration
# ============================================================================

# Optimized weights based on A/B testing (Task 12)
# Alternative weights showed better correlation with human judgments
# Previous: Route 15%, Retrieval 25%, Fact 40%, Quality 15%, Cite 5%
# Optimized: Route 10%, Retrieval 30%, Fact 45%, Quality 10%, Cite 5%
QUALITY_WEIGHT_ROUTE: Final[float] = _get_float_env("QUALITY_WEIGHT_ROUTE", 0.10)
QUALITY_WEIGHT_RETRIEVAL: Final[float] = _get_float_env("QUALITY_WEIGHT_RETRIEVAL", 0.30)
QUALITY_WEIGHT_ANSWER_FACT: Final[float] = _get_float_env("QUALITY_WEIGHT_ANSWER_FACT", 0.45)
QUALITY_WEIGHT_ANSWER_QUALITY: Final[float] = _get_float_env("QUALITY_WEIGHT_ANSWER_QUALITY", 0.10)
QUALITY_WEIGHT_CITATION: Final[float] = _get_float_env("QUALITY_WEIGHT_CITATION", 0.05)
QUALITY_HIGH_THRESHOLD: Final[float] = _get_float_env("QUALITY_HIGH_THRESHOLD", 0.85)
QUALITY_MEDIUM_THRESHOLD: Final[float] = _get_float_env("QUALITY_MEDIUM_THRESHOLD", 0.70)
QUALITY_LOW_THRESHOLD: Final[float] = _get_float_env("QUALITY_LOW_THRESHOLD", 0.50)


# ============================================================================
# Context Tracker Configuration
# ============================================================================

CONTEXT_MAX_HISTORY_TURNS: Final[int] = _get_int_env("CONTEXT_MAX_HISTORY_TURNS", 10)
CONTEXT_SUMMARY_FREQUENCY: Final[int] = _get_int_env("CONTEXT_SUMMARY_FREQUENCY", 5)
CONTEXT_SUMMARY_MIN_TURNS: Final[int] = _get_int_env("CONTEXT_SUMMARY_MIN_TURNS", 3)
CONTEXT_TTL_SECONDS: Final[int] = _get_int_env("CONTEXT_TTL_SECONDS", 3600)


# ============================================================================
# Retry Strategy Configuration
# ============================================================================

MAX_ROUTE_RETRIES: Final[int] = _get_int_env("MAX_ROUTE_RETRIES", 1)
MAX_ANSWER_RETRIES: Final[int] = _get_int_env("MAX_ANSWER_RETRIES", 1)
MAX_TOTAL_RETRIES: Final[int] = _get_int_env("MAX_TOTAL_RETRIES", 2)
MAX_TOTAL_TIME_MS: Final[int] = _get_int_env("MAX_TOTAL_TIME_MS", 10000)
ROUTE_VALIDATOR_TIMEOUT_MS: Final[int] = _get_int_env("ROUTE_VALIDATOR_TIMEOUT_MS", 500)
RETRIEVAL_QUALITY_TIMEOUT_MS: Final[int] = _get_int_env("RETRIEVAL_QUALITY_TIMEOUT_MS", 200)
ANSWER_VALIDATOR_TIMEOUT_MS: Final[int] = _get_int_env("ANSWER_VALIDATOR_TIMEOUT_MS", 1000)


# ============================================================================
# Performance Monitoring Configuration
# ============================================================================

PERF_THRESHOLD_FAST: Final[int] = _get_int_env("PERF_THRESHOLD_FAST", 2000)
PERF_THRESHOLD_MEDIUM: Final[int] = _get_int_env("PERF_THRESHOLD_MEDIUM", 5000)
PERF_THRESHOLD_SLOW: Final[int] = _get_int_env("PERF_THRESHOLD_SLOW", 8000)
ENABLE_PERFORMANCE_LOGGING: Final[bool] = _get_bool_env("ENABLE_PERFORMANCE_LOGGING", True)


# ============================================================================
# Fallback Configuration
# ============================================================================

FALLBACK_ROUTE_MAP: Final[dict] = {
    "hybrid": "vector",
    "graph": "vector",
    "react": "vector"
}
ENABLE_AUTO_FALLBACK: Final[bool] = _get_bool_env("ENABLE_AUTO_FALLBACK", True)
