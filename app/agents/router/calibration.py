"""
Router confidence calibration system.

Calibrates raw confidence scores to better reflect actual routing accuracy
by tracking historical performance in confidence buckets.

Key features:
- Bucket-based calibration (0.5-0.6, 0.6-0.7, 0.7-0.8, 0.8-0.9, 0.9-1.0)
- Historical accuracy tracking per bucket
- Persistent storage of calibration data
- Minimum sample requirements to prevent overfitting
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

# Configuration constants
CONFIDENCE_BUCKETS: Final[list[tuple[float, float]]] = [
    (0.5, 0.6),
    (0.6, 0.7),
    (0.7, 0.8),
    (0.8, 0.9),
    (0.9, 1.0),
]

MIN_SAMPLES_FOR_CALIBRATION: Final[int] = 5  # Minimum predictions before applying calibration
DEFAULT_ACCURACY: Final[float] = 0.5  # Default accuracy when no history

# Configuration file path - anchored at repository root
REPOSITORY_ROOT: Final[Path] = Path(__file__).resolve().parents[3]
CALIBRATION_CONFIG_PATH: Final[Path] = REPOSITORY_ROOT / "config" / "router_calibration.json"
"""Tracked starter distribution; accumulated outcomes go to ROUTER_CALIBRATION_PATH."""

_FLUSH_EVERY: Final[int] = 20


def get_bucket_for_confidence(confidence: float) -> str:
    """
    Get the bucket name for a given confidence score.

    Args:
        confidence: Raw confidence score

    Returns:
        Bucket name (e.g., "0.7-0.8")
    """
    # Clamp to valid range
    confidence = max(CONFIDENCE_BUCKETS[0][0], min(CONFIDENCE_BUCKETS[-1][1], confidence))

    # Each bucket is half-open except the last, whose upper bound has to be
    # inclusive or the clamped maximum belongs to no bucket at all. Saying that
    # positionally rather than as `confidence == 1.0 and high == 1.0` keeps it
    # true if the table ever stops ending at 1.0 -- that spelling sent the top
    # value to the *lowest* bucket via the fallback below the moment it did.
    last = len(CONFIDENCE_BUCKETS) - 1
    for index, (low, high) in enumerate(CONFIDENCE_BUCKETS):
        if low <= confidence < high or (index == last and confidence <= high):
            return f"{low}-{high}"

    # Unreachable while the table is contiguous; kept so a gap in it degrades
    # to a bucket rather than to an exception.
    return f"{CONFIDENCE_BUCKETS[0][0]}-{CONFIDENCE_BUCKETS[0][1]}"


@dataclass
class CalibrationBucket:
    """Calibration data for a confidence bucket."""

    total_predictions: int = 0
    correct_predictions: int = 0
    last_updated: str | None = None
    low: float = 0.5
    high: float = 1.0

    @property
    def historical_accuracy(self) -> float:
        """Calculate historical accuracy for this bucket."""
        if self.total_predictions == 0:
            return DEFAULT_ACCURACY
        return self.correct_predictions / self.total_predictions

    @property
    def midpoint(self) -> float:
        """Calculate the midpoint of this bucket's range."""
        return (self.low + self.high) / 2.0

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "total_predictions": self.total_predictions,
            "correct_predictions": self.correct_predictions,
            "last_updated": self.last_updated,
            "low": self.low,
            "high": self.high,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "CalibrationBucket":
        """Create from dictionary."""
        return cls(
            total_predictions=data.get("total_predictions", 0),
            correct_predictions=data.get("correct_predictions", 0),
            last_updated=data.get("last_updated"),
            low=data.get("low", 0.5),
            high=data.get("high", 1.0),
        )


@dataclass
class CalibrationData:
    """Complete calibration data for all buckets."""

    buckets: dict[str, CalibrationBucket] = field(default_factory=dict)
    version: str = "1.0"

    def __post_init__(self):
        """Initialize all buckets if not provided."""
        if not self.buckets:
            self.buckets = {f"{low}-{high}": CalibrationBucket(low=low, high=high) for low, high in CONFIDENCE_BUCKETS}

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {"version": self.version, "buckets": {name: bucket.to_dict() for name, bucket in self.buckets.items()}}

    @classmethod
    def from_dict(cls, data: dict) -> "CalibrationData":
        """Create from dictionary."""
        buckets = {
            name: CalibrationBucket.from_dict(bucket_data) for name, bucket_data in data.get("buckets", {}).items()
        }

        # Boundaries belong to the bucketing scheme, not to the accumulated
        # data: the bucket's own name encodes them, so a persisted pair can only
        # ever agree with the table or be wrong. Taking them from the table
        # unconditionally replaces a guess -- "these are still 0.5/1.0, so the
        # file must predate storing them" -- which could not tell an absent
        # boundary from a genuine one, and needed a special case for the first
        # bucket to paper over that.
        for low, high in CONFIDENCE_BUCKETS:
            bucket_name = f"{low}-{high}"
            bucket = buckets.get(bucket_name)
            if bucket is None:
                buckets[bucket_name] = CalibrationBucket(low=low, high=high)
            else:
                bucket.low = low
                bucket.high = high

        return cls(buckets=buckets, version=data.get("version", "1.0"))


def load_calibration_data(config_path: Path | None = None) -> CalibrationData:
    """
    Load calibration data from file.

    Args:
        config_path: Path to calibration config file (defaults to config/router_calibration.json)

    Returns:
        CalibrationData instance (new if file doesn't exist)
    """
    if config_path is None:
        config_path = CALIBRATION_CONFIG_PATH

    try:
        if config_path.exists():
            with open(config_path) as f:
                data_dict = json.load(f)
                return CalibrationData.from_dict(data_dict)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning(f"Failed to load calibration data from {config_path}: {e}")

    # Return fresh data if load failed
    return CalibrationData()


def save_calibration_data(data: CalibrationData, config_path: Path | None = None) -> None:
    """
    Save calibration data to file.

    Args:
        data: CalibrationData to save
        config_path: Path to calibration config file (defaults to config/router_calibration.json)
    """
    if config_path is None:
        config_path = CALIBRATION_CONFIG_PATH

    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump(data.to_dict(), f, indent=2)
        logger.debug(f"Saved calibration data to {config_path}")
    except OSError as e:
        logger.error(f"Failed to save calibration data to {config_path}: {e}")


def update_calibration_data(data: CalibrationData, raw_confidence: float, was_correct: bool) -> None:
    """
    Update calibration data with feedback from a routing decision.

    Args:
        data: CalibrationData to update
        raw_confidence: Raw confidence score that was used
        was_correct: Whether the routing decision was correct
    """
    bucket_name = get_bucket_for_confidence(raw_confidence)
    bucket = data.buckets[bucket_name]

    bucket.total_predictions += 1
    if was_correct:
        bucket.correct_predictions += 1
    bucket.last_updated = datetime.now().isoformat()

    logger.debug(
        f"Updated calibration bucket {bucket_name}: "
        f"{bucket.correct_predictions}/{bucket.total_predictions} "
        f"(accuracy={bucket.historical_accuracy:.2f})"
    )


def apply_calibration(raw_confidence: float, data: CalibrationData) -> float:
    """
    Apply calibration to a raw confidence score.

    Calibration formula:
        calibrated = raw_confidence * (historical_accuracy / bucket_midpoint)

    This adjusts the confidence to match the historical accuracy observed
    for similar confidence levels while preserving within-bucket variation.

    Example:
        - Bucket 0.7-0.8 (midpoint=0.75) with historical_accuracy=0.8
        - raw_confidence=0.79 → calibrated = 0.79 * (0.8/0.75) = 0.843
        - raw_confidence=0.71 → calibrated = 0.71 * (0.8/0.75) = 0.757

    Args:
        raw_confidence: Raw confidence score from router
        data: Calibration data with historical accuracy

    Returns:
        Calibrated confidence score clamped to [0.0, 1.0]
    """
    bucket_name = get_bucket_for_confidence(raw_confidence)
    bucket = data.buckets[bucket_name]

    # Require minimum samples before calibrating
    if bucket.total_predictions < MIN_SAMPLES_FOR_CALIBRATION:
        logger.debug(
            f"Not enough samples for calibration in bucket {bucket_name} "
            f"({bucket.total_predictions} < {MIN_SAMPLES_FOR_CALIBRATION})"
        )
        return raw_confidence

    # Apply calibration: scale by ratio of historical accuracy to bucket midpoint
    historical_accuracy = bucket.historical_accuracy
    bucket_midpoint = bucket.midpoint
    calibrated = raw_confidence * (historical_accuracy / bucket_midpoint)

    # Clamp to valid range
    calibrated = max(0.0, min(1.0, calibrated))

    logger.debug(
        f"Calibrated confidence {raw_confidence:.2f} -> {calibrated:.2f} "
        f"(bucket={bucket_name}, history={historical_accuracy:.2f}, midpoint={bucket_midpoint:.2f})"
    )

    return calibrated


class ConfidenceCalibrator:
    """
    Manages confidence calibration for router decisions.

    Usage:
        calibrator = ConfidenceCalibrator()

        # Apply calibration
        calibrated = calibrator.calibrate(raw_confidence=0.85)

        # Record feedback
        calibrator.record_feedback(raw_confidence=0.85, was_correct=True)
    """

    def __init__(self, config_path: Path | None = None):
        """
        Initialize calibrator.

        Args:
            config_path: Where accumulated outcomes are stored. Defaults to
                ROUTER_CALIBRATION_PATH under data/, seeded once from the
                tracked config/router_calibration.json starter file.

        Accumulated outcomes are runtime state. Writing them into the tracked
        `config/` file, which is what this used to do, meant every request dirtied
        a checked-in file.
        """
        if config_path is None:
            from app.core.config import get_settings

            config_path = get_settings().router_calibration_path

        self.config_path = config_path
        if config_path.exists():
            self.calibration_data = load_calibration_data(config_path)
        else:
            # Seed from the shipped starter so a fresh deployment does not begin
            # with an empty distribution.
            self.calibration_data = load_calibration_data(CALIBRATION_CONFIG_PATH)
        self._unsaved = 0

    def calibrate(self, raw_confidence: float) -> float:
        """
        Apply calibration to a raw confidence score.

        Args:
            raw_confidence: Raw confidence from router

        Returns:
            Calibrated confidence score
        """
        return apply_calibration(raw_confidence, self.calibration_data)

    def record_feedback(self, raw_confidence: float, was_correct: bool) -> None:
        """
        Record feedback about a routing decision.

        Args:
            raw_confidence: Raw confidence that was used
            was_correct: Whether the decision was correct

        Updates in memory every time and persists every `_FLUSH_EVERY` records.
        This used to write the file synchronously on each call, which put a disk
        write on the request path for a statistic that is only read at startup.
        """
        update_calibration_data(self.calibration_data, raw_confidence, was_correct)
        self._unsaved += 1
        if self._unsaved >= _FLUSH_EVERY:
            self.flush()

    def flush(self) -> None:
        """Persist accumulated outcomes."""
        if not self._unsaved:
            return
        save_calibration_data(self.calibration_data, self.config_path)
        self._unsaved = 0

    def get_stats(self) -> dict[str, dict]:
        """
        Get calibration statistics for all buckets.

        Returns:
            Dictionary mapping bucket names to stats
        """
        return {
            name: {
                "total_predictions": bucket.total_predictions,
                "correct_predictions": bucket.correct_predictions,
                "historical_accuracy": bucket.historical_accuracy,
                "last_updated": bucket.last_updated,
            }
            for name, bucket in self.calibration_data.buckets.items()
        }
