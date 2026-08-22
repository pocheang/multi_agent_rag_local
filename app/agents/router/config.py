"""
Router module configuration.

Combines router-specific constants and hybrid clarification settings.
"""

import os
from typing import Final

# ============================================================================
# Router Decision Configuration
# ============================================================================

# Confidence calibration
ENABLE_CALIBRATION: Final[bool] = os.getenv("ENABLE_CALIBRATION", "false").lower() == "true"

# Web route control
DISABLE_WEB_ROUTE: Final[bool] = os.getenv("DISABLE_WEB_ROUTE", "false").lower() == "true"
ENABLE_WEB_ROUTE_DOWNGRADE: Final[bool] = os.getenv("ENABLE_WEB_ROUTE_DOWNGRADE", "false").lower() == "true"

# Reasoning model fallback
USE_REASONING_FOR_LOW_CONFIDENCE: Final[bool] = os.getenv("USE_REASONING_FOR_LOW_CONFIDENCE", "false").lower() == "true"

# Router accuracy tracking
ENABLE_ROUTER_ACCURACY_TRACKING: Final[bool] = os.getenv("ENABLE_ROUTER_ACCURACY_TRACKING", "false").lower() == "true"

ROUTER_ACCURACY_LOG_FILE: Final[str] = os.getenv("ROUTER_ACCURACY_LOG_FILE", "logs/router_accuracy.jsonl")

# ============================================================================
# Hybrid Clarification Configuration (from hybrid_config.py)
# ============================================================================

# Enable hybrid clarification mode (rule + LLM fallback)
USE_HYBRID_CLARIFICATION: Final[bool] = os.getenv("USE_HYBRID_CLARIFICATION", "false").lower() == "true"

# LLM fallback threshold: use LLM when rule confidence is below this
LLM_FALLBACK_THRESHOLD: Final[float] = float(os.getenv("LLM_FALLBACK_THRESHOLD", "0.8"))

# LLM-enhanced information extraction
LLM_ENHANCED_EXTRACTION: Final[bool] = os.getenv("LLM_ENHANCED_EXTRACTION", "false").lower() == "true"

# LLM dynamic question generation
LLM_DYNAMIC_QUESTIONS: Final[bool] = os.getenv("LLM_DYNAMIC_QUESTIONS", "false").lower() == "true"


# ============================================================================
# Helper Functions
# ============================================================================


def should_disable_web_route() -> bool:
    """Check if web route should be disabled."""
    return DISABLE_WEB_ROUTE


def should_use_reasoning_fallback() -> bool:
    """Check if reasoning model should be used for low confidence routes."""
    return USE_REASONING_FOR_LOW_CONFIDENCE
