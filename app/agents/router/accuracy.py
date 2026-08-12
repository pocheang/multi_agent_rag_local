"""
Route Accuracy Tracker - Historical accuracy tracking for route validation.

Tracks actual routing outcomes and builds accuracy models per route type
and query pattern to enable confidence recalibration.
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.agents.router.routing import RouteDecision

logger = logging.getLogger(__name__)

# Configuration
MIN_SAMPLES_FOR_RECALIBRATION = 5
AUTO_SAVE_INTERVAL = 10  # Save every N records
DEFAULT_ACCURACY = 0.5
RECALIBRATION_WEIGHT = 0.7  # How much to weight historical accuracy vs original confidence
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


@dataclass
class RouteOutcome:
    """Single route outcome record"""
    query: str
    route: str
    skill: str
    agent_class: str
    confidence: float
    was_successful: bool
    execution_time_ms: int
    timestamp: datetime
    reason: str = ""

    def to_dict(self):
        """Convert to dictionary for JSON serialization"""
        return {
            "query": self.query,
            "route": self.route,
            "skill": self.skill,
            "agent_class": self.agent_class,
            "confidence": self.confidence,
            "was_successful": self.was_successful,
            "execution_time_ms": self.execution_time_ms,
            "timestamp": self.timestamp.isoformat(),
            "reason": self.reason
        }

    @classmethod
    def from_dict(cls, data: dict):
        """Create from dictionary"""
        return cls(
            query=data["query"],
            route=data["route"],
            skill=data["skill"],
            agent_class=data["agent_class"],
            confidence=data["confidence"],
            was_successful=data["was_successful"],
            execution_time_ms=data["execution_time_ms"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            reason=data.get("reason", "")
        )


@dataclass
class AccuracyStats:
    """Accuracy statistics for a subset of routes"""
    total_routes: int
    successful_routes: int

    @property
    def accuracy_rate(self) -> float:
        """Calculate accuracy rate with default for empty stats"""
        if self.total_routes == 0:
            return DEFAULT_ACCURACY
        return self.successful_routes / self.total_routes


class RouteAccuracyTracker:
    """
    Tracks historical route accuracy and provides confidence recalibration.

    Features:
    - Records actual routing outcomes (success/failure)
    - Builds accuracy models per route type, skill, confidence bucket
    - Recalibrates confidence based on historical performance
    - Persists data to JSON file
    """

    def __init__(self, storage_file: Optional[Path] = None):
        """
        Initialize tracker.

        Args:
            storage_file: Path to JSON storage file (default: config/route_accuracy.json)
        """
        if storage_file is None:
            storage_file = REPOSITORY_ROOT / "config" / "route_accuracy.json"

        self.storage_file = Path(storage_file)
        self.outcomes: list[RouteOutcome] = []
        self.record_count = 0

    def record_outcome(
        self,
        query: str,
        route_decision: RouteDecision,
        was_successful: bool,
        execution_time_ms: int
    ):
        """
        Record a routing outcome.

        Args:
            query: Original query text
            route_decision: Router's decision
            was_successful: Whether the route produced good results
            execution_time_ms: Execution time
        """
        outcome = RouteOutcome(
            query=query,
            route=route_decision.route,
            skill=route_decision.skill,
            agent_class=route_decision.agent_class,
            confidence=route_decision.confidence,
            was_successful=was_successful,
            execution_time_ms=execution_time_ms,
            timestamp=datetime.now(),
            reason=route_decision.reason
        )

        self.outcomes.append(outcome)
        self.record_count += 1

        # Auto-save every N records
        if self.record_count % AUTO_SAVE_INTERVAL == 0:
            self.save()

    def get_accuracy_stats(
        self,
        route: Optional[str] = None,
        skill: Optional[str] = None,
        agent_class: Optional[str] = None,
        confidence_min: Optional[float] = None,
        confidence_max: Optional[float] = None,
        query_pattern: Optional[str] = None
    ) -> AccuracyStats:
        """
        Get accuracy statistics filtered by criteria.

        Args:
            route: Filter by route type
            skill: Filter by skill
            agent_class: Filter by agent class
            confidence_min: Minimum confidence threshold
            confidence_max: Maximum confidence threshold
            query_pattern: Filter by query pattern (substring match)

        Returns:
            AccuracyStats with filtered results
        """
        filtered = self.outcomes

        if route is not None:
            filtered = [o for o in filtered if o.route == route]

        if skill is not None:
            filtered = [o for o in filtered if o.skill == skill]

        if agent_class is not None:
            filtered = [o for o in filtered if o.agent_class == agent_class]

        if confidence_min is not None:
            filtered = [o for o in filtered if o.confidence >= confidence_min]

        if confidence_max is not None:
            filtered = [o for o in filtered if o.confidence <= confidence_max]

        if query_pattern is not None:
            filtered = [o for o in filtered if query_pattern.lower() in o.query.lower()]

        total = len(filtered)
        successful = sum(1 for o in filtered if o.was_successful)

        return AccuracyStats(total_routes=total, successful_routes=successful)

    def recalibrate_confidence(self, route_decision: RouteDecision) -> float:
        """
        Recalibrate confidence based on historical accuracy.

        Uses historical performance of similar routes to adjust confidence.
        Blends original confidence with historical accuracy.

        Args:
            route_decision: Router decision to recalibrate

        Returns:
            Recalibrated confidence score
        """
        # Get historical accuracy for this route + confidence bucket
        confidence_bucket_size = 0.15
        confidence_min = max(0.5, route_decision.confidence - confidence_bucket_size / 2)
        confidence_max = min(1.0, route_decision.confidence + confidence_bucket_size / 2)

        stats = self.get_accuracy_stats(
            route=route_decision.route,
            confidence_min=confidence_min,
            confidence_max=confidence_max
        )

        # Need minimum samples for recalibration
        if stats.total_routes < MIN_SAMPLES_FOR_RECALIBRATION:
            return route_decision.confidence

        # Blend original confidence with historical accuracy
        historical_accuracy = stats.accuracy_rate
        recalibrated = (
            RECALIBRATION_WEIGHT * historical_accuracy +
            (1 - RECALIBRATION_WEIGHT) * route_decision.confidence
        )

        # Clamp to valid range
        return max(0.0, min(1.0, recalibrated))

    def save(self):
        """Save tracking data to JSON file"""
        # Ensure directory exists
        self.storage_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "outcomes": [o.to_dict() for o in self.outcomes],
            "last_updated": datetime.now().isoformat()
        }

        with open(self.storage_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        logger.info(f"Saved {len(self.outcomes)} outcomes to {self.storage_file}")

    def load(self):
        """Load tracking data from JSON file"""
        if not self.storage_file.exists():
            logger.info(f"No existing tracking data at {self.storage_file}")
            return

        try:
            with open(self.storage_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            self.outcomes = [RouteOutcome.from_dict(o) for o in data.get("outcomes", [])]
            logger.info(f"Loaded {len(self.outcomes)} outcomes from {self.storage_file}")

        except Exception as e:
            logger.error(f"Failed to load tracking data: {e}")
            self.outcomes = []
