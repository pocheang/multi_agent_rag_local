"""
Router configuration for calibration parameters.

Externalizes calibration settings to support tuning without code changes.
"""

from typing import Final

# ============================================================================
# Confidence Calibration Configuration
# ============================================================================

# Minimum number of predictions in a bucket before applying calibration
# Higher values = more conservative (requires more data before adjusting)
# Lower values = more aggressive (adjusts confidence sooner)
MIN_SAMPLES_FOR_CALIBRATION: Final[int] = 5

# Default accuracy to assume when no historical data exists
# 0.5 = neutral assumption (50% accuracy)
DEFAULT_HISTORICAL_ACCURACY: Final[float] = 0.5

# Confidence bucket boundaries
# Predictions are grouped into these ranges for calibration tracking
CONFIDENCE_BUCKET_BOUNDARIES: Final[list[tuple[float, float]]] = [
    (0.5, 0.6),  # Low confidence
    (0.6, 0.7),  # Below average
    (0.7, 0.8),  # Average
    (0.8, 0.9),  # Above average
    (0.9, 1.0),  # High confidence
]

# ============================================================================
# Cache Versioning Configuration
# ============================================================================

# Cache version for router decisions
# Increment this when calibration logic changes to invalidate old cached decisions
ROUTER_CACHE_VERSION: Final[str] = "v2_calibrated"

# Whether to include cache version in cache keys
# True = separate caches for different calibration versions
# False = share cache across versions (may return stale calibrated values)
USE_CACHE_VERSIONING: Final[bool] = True

# ============================================================================
# Calibration Persistence Configuration
# ============================================================================

# Filename for calibration data storage
CALIBRATION_DATA_FILE: Final[str] = "router_calibration.json"

# Whether to auto-save calibration data after each feedback
# True = immediate persistence (safer, slight performance cost)
# False = manual save required (faster, risk of data loss)
AUTO_SAVE_CALIBRATION: Final[bool] = True

# ============================================================================
# Calibration Behavior Configuration
# ============================================================================

# Whether to enable confidence calibration
# Set to False to disable calibration and use raw confidence scores
ENABLE_CALIBRATION: Final[bool] = True
