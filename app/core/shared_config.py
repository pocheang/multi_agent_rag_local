"""
Shared configuration constants used across multiple layers.

This module contains configuration that needs to be shared between:
- app/services/ (service layer)
- app/agents/ (component layer)
- app/orchestration/ (orchestration layer)

Design principle: Keep this minimal. Most configuration should be
component-specific and live in the component's own module.
"""

import os
from typing import Final


def _get_bool_env(key: str, default: bool) -> bool:
    """Get boolean from environment variable."""
    return os.getenv(key, str(default)).lower() in ("true", "1", "yes")


def _get_int_env(key: str, default: int) -> int:
    """Get integer from environment variable."""
    return int(os.getenv(key, str(default)))


# ============================================================================
# Context Tracking Configuration
# ============================================================================

CONTEXT_MAX_HISTORY_TURNS: Final[int] = _get_int_env("CONTEXT_MAX_HISTORY_TURNS", 10)
CONTEXT_SUMMARY_FREQUENCY: Final[int] = _get_int_env("CONTEXT_SUMMARY_FREQUENCY", 5)
CONTEXT_SUMMARY_MIN_TURNS: Final[int] = _get_int_env("CONTEXT_SUMMARY_MIN_TURNS", 3)
CONTEXT_TTL_SECONDS: Final[int] = _get_int_env("CONTEXT_TTL_SECONDS", 3600)

# ============================================================================
# Quality & Validation Configuration
# ============================================================================

ENABLE_QUALITY_VALIDATION: Final[bool] = _get_bool_env("ENABLE_QUALITY_VALIDATION", True)
ENABLE_CONTEXT_TRACKING: Final[bool] = _get_bool_env("ENABLE_CONTEXT_TRACKING", True)

# ============================================================================
# Performance Thresholds
# ============================================================================

PERF_THRESHOLD_FAST: Final[int] = _get_int_env("PERF_THRESHOLD_FAST", 2000)
PERF_THRESHOLD_MEDIUM: Final[int] = _get_int_env("PERF_THRESHOLD_MEDIUM", 5000)
PERF_THRESHOLD_SLOW: Final[int] = _get_int_env("PERF_THRESHOLD_SLOW", 8000)
