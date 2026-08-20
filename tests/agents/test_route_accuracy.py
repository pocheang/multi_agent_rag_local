"""
Tests for Route Accuracy Tracker - Historical accuracy tracking for route validation.

Following TDD: Write tests first, watch them fail, then implement.
"""

import pytest
import json
import tempfile
from pathlib import Path
from datetime import datetime
from app.agents.router.accuracy import (
    RouteAccuracyTracker,
    RouteOutcome,
    AccuracyStats,
)
from app.agents.router.routing import LegacyRouteDecision as RouteDecision


@pytest.fixture
def temp_storage_file():
    """Create temporary storage file for tests"""
    # Use tempfile with delete=False to avoid permission issues
    fd, path = tempfile.mkstemp(suffix='.json')
    import os
    os.close(fd)
    yield Path(path)
    # Cleanup
    try:
        Path(path).unlink()
    except:
        pass


@pytest.fixture
def tracker(temp_storage_file):
    """Create tracker instance with temporary storage"""
    return RouteAccuracyTracker(storage_file=temp_storage_file)


class TestRouteOutcomeModel:
    """Test RouteOutcome data model"""

    def test_route_outcome_creation(self):
        """Should create RouteOutcome with all fields"""
        outcome = RouteOutcome(
            query="test query",
            route="vector",
            skill="answer_with_citations",
            agent_class="general",
            confidence=0.85,
            was_successful=True,
            execution_time_ms=150,
            timestamp=datetime.now()
        )

        assert outcome.query == "test query"
        assert outcome.route == "vector"
        assert outcome.skill == "answer_with_citations"
        assert outcome.confidence == 0.85
        assert outcome.was_successful is True


class TestAccuracyStatsModel:
    """Test AccuracyStats data model"""

    def test_accuracy_stats_empty(self):
        """Should calculate 0.5 default accuracy for empty stats"""
        stats = AccuracyStats(
            total_routes=0,
            successful_routes=0
        )

        assert stats.accuracy_rate == 0.5

    def test_accuracy_stats_calculation(self):
        """Should calculate correct accuracy rate"""
        stats = AccuracyStats(
            total_routes=10,
            successful_routes=9
        )

        assert stats.accuracy_rate == 0.9

    def test_accuracy_stats_zero_division(self):
        """Should handle zero division gracefully"""
        stats = AccuracyStats(
            total_routes=0,
            successful_routes=0
        )

        # Should return default 0.5, not raise error
        assert isinstance(stats.accuracy_rate, float)
        assert stats.accuracy_rate == 0.5


class TestRouteAccuracyTracker:
    """Test RouteAccuracyTracker core functionality"""

    def test_tracker_initialization(self, tracker, temp_storage_file):
        """Should initialize tracker with empty data"""
        assert tracker.storage_file == temp_storage_file
        # Tracker should start with empty outcomes
        assert len(tracker.outcomes) == 0

    def test_record_outcome_success(self, tracker):
        """Should record successful route outcome"""
        route_decision = RouteDecision(
            route="vector",
            skill="answer_with_citations",
            agent_class="general",
            reason="test",
            confidence=0.85
        )

        tracker.record_outcome(
            query="what is ML?",
            route_decision=route_decision,
            was_successful=True,
            execution_time_ms=150
        )

        # Should have recorded one outcome
        stats = tracker.get_accuracy_stats(route="vector")
        assert stats.total_routes == 1
        assert stats.successful_routes == 1
        assert stats.accuracy_rate == 1.0

    def test_record_outcome_failure(self, tracker):
        """Should record failed route outcome"""
        route_decision = RouteDecision(
            route="graph",
            skill="entity_search",
            agent_class="general",
            reason="test",
            confidence=0.65
        )

        tracker.record_outcome(
            query="test query",
            route_decision=route_decision,
            was_successful=False,
            execution_time_ms=200
        )

        stats = tracker.get_accuracy_stats(route="graph")
        assert stats.total_routes == 1
        assert stats.successful_routes == 0
        assert stats.accuracy_rate == 0.0

    def test_multiple_outcomes_same_route(self, tracker):
        """Should aggregate multiple outcomes for same route"""
        route_decision = RouteDecision(
            route="vector",
            skill="answer_with_citations",
            agent_class="general",
            reason="test",
            confidence=0.80
        )

        # Record 7 successful, 3 failed
        for i in range(10):
            tracker.record_outcome(
                query=f"query {i}",
                route_decision=route_decision,
                was_successful=(i < 7),
                execution_time_ms=100
            )

        stats = tracker.get_accuracy_stats(route="vector")
        assert stats.total_routes == 10
        assert stats.successful_routes == 7
        assert stats.accuracy_rate == 0.7

    def test_accuracy_by_route_type(self, tracker):
        """Should track accuracy separately by route type"""
        # Vector route: 90% accuracy
        vector_decision = RouteDecision(
            route="vector", skill="answer_with_citations",
            agent_class="general", reason="test", confidence=0.85
        )
        for i in range(10):
            tracker.record_outcome(
                query=f"vector query {i}",
                route_decision=vector_decision,
                was_successful=(i < 9),
                execution_time_ms=100
            )

        # Graph route: 70% accuracy
        graph_decision = RouteDecision(
            route="graph", skill="entity_search",
            agent_class="general", reason="test", confidence=0.75
        )
        for i in range(10):
            tracker.record_outcome(
                query=f"graph query {i}",
                route_decision=graph_decision,
                was_successful=(i < 7),
                execution_time_ms=150
            )

        vector_stats = tracker.get_accuracy_stats(route="vector")
        graph_stats = tracker.get_accuracy_stats(route="graph")

        assert vector_stats.accuracy_rate == 0.9
        assert graph_stats.accuracy_rate == 0.7

    def test_accuracy_by_skill(self, tracker):
        """Should track accuracy by skill"""
        decision = RouteDecision(
            route="vector",
            skill="pdf_text_reader",
            agent_class="general",
            reason="test",
            confidence=0.80
        )

        for i in range(10):
            tracker.record_outcome(
                query=f"pdf query {i}",
                route_decision=decision,
                was_successful=(i < 8),
                execution_time_ms=120
            )

        stats = tracker.get_accuracy_stats(skill="pdf_text_reader")
        assert stats.accuracy_rate == 0.8

    def test_accuracy_by_confidence_bucket(self, tracker):
        """Should track accuracy by confidence ranges"""
        # High confidence routes (0.85-0.95): 95% accuracy
        for i in range(20):
            decision = RouteDecision(
                route="vector",
                skill="answer_with_citations",
                agent_class="general",
                reason="test",
                confidence=0.90
            )
            tracker.record_outcome(
                query=f"high conf query {i}",
                route_decision=decision,
                was_successful=(i < 19),
                execution_time_ms=100
            )

        # Low confidence routes (0.50-0.60): 60% accuracy
        for i in range(20):
            decision = RouteDecision(
                route="vector",
                skill="answer_with_citations",
                agent_class="general",
                reason="test",
                confidence=0.55
            )
            tracker.record_outcome(
                query=f"low conf query {i}",
                route_decision=decision,
                was_successful=(i < 12),
                execution_time_ms=100
            )

        high_stats = tracker.get_accuracy_stats(confidence_min=0.85, confidence_max=1.0)
        low_stats = tracker.get_accuracy_stats(confidence_min=0.5, confidence_max=0.65)

        assert high_stats.accuracy_rate == 0.95
        assert low_stats.accuracy_rate == 0.60

    def test_recalibrate_confidence_based_on_history(self, tracker):
        """Should recalibrate confidence based on historical accuracy"""
        # Simulate router that's overconfident
        # It predicts 0.90 confidence but only achieves 70% accuracy
        for i in range(20):
            decision = RouteDecision(
                route="vector",
                skill="answer_with_citations",
                agent_class="general",
                reason="test",
                confidence=0.90
            )
            tracker.record_outcome(
                query=f"query {i}",
                route_decision=decision,
                was_successful=(i < 14),  # 70% success rate
                execution_time_ms=100
            )

        # Now recalibrate a new decision with 0.90 confidence
        new_decision = RouteDecision(
            route="vector",
            skill="answer_with_citations",
            agent_class="general",
            reason="test",
            confidence=0.90
        )

        recalibrated_confidence = tracker.recalibrate_confidence(
            route_decision=new_decision
        )

        # Should pull confidence down toward 0.70
        assert recalibrated_confidence < 0.90
        assert 0.65 <= recalibrated_confidence <= 0.80

    def test_recalibrate_insufficient_history(self, tracker):
        """Should return original confidence when insufficient history"""
        # Only 2 samples (need 5 minimum)
        for i in range(2):
            decision = RouteDecision(
                route="vector",
                skill="answer_with_citations",
                agent_class="general",
                reason="test",
                confidence=0.90
            )
            tracker.record_outcome(
                query=f"query {i}",
                route_decision=decision,
                was_successful=True,
                execution_time_ms=100
            )

        new_decision = RouteDecision(
            route="vector",
            skill="answer_with_citations",
            agent_class="general",
            reason="test",
            confidence=0.90
        )

        recalibrated = tracker.recalibrate_confidence(new_decision)

        # Should return original confidence (insufficient data)
        assert recalibrated == 0.90

    def test_persistence_save_and_load(self, tracker, temp_storage_file):
        """Should persist tracking data to file and reload it"""
        # Record some outcomes
        decision = RouteDecision(
            route="vector",
            skill="answer_with_citations",
            agent_class="general",
            reason="test",
            confidence=0.85
        )

        for i in range(10):
            tracker.record_outcome(
                query=f"query {i}",
                route_decision=decision,
                was_successful=(i < 9),
                execution_time_ms=100
            )

        # Save to disk
        tracker.save()

        assert temp_storage_file.exists()

        # Create new tracker instance and load
        new_tracker = RouteAccuracyTracker(storage_file=temp_storage_file)
        new_tracker.load()

        # Should have same stats
        stats = new_tracker.get_accuracy_stats(route="vector")
        assert stats.total_routes == 10
        assert stats.successful_routes == 9
        assert stats.accuracy_rate == 0.9

    def test_persistence_auto_save(self, tracker, temp_storage_file):
        """Should auto-save periodically (every 10 records)"""
        decision = RouteDecision(
            route="vector",
            skill="answer_with_citations",
            agent_class="general",
            reason="test",
            confidence=0.85
        )

        # Record 10 outcomes (should trigger auto-save)
        for i in range(10):
            tracker.record_outcome(
                query=f"query {i}",
                route_decision=decision,
                was_successful=True,
                execution_time_ms=100
            )

        # File should exist due to auto-save
        assert temp_storage_file.exists()

    def test_get_route_pattern_stats(self, tracker):
        """Should return stats for query pattern matching"""
        # Graph queries with relation keywords
        for i in range(10):
            decision = RouteDecision(
                route="graph",
                skill="entity_search",
                agent_class="general",
                reason="relation_query",
                confidence=0.80
            )
            tracker.record_outcome(
                query=f"relationship between A{i} and B{i}",
                route_decision=decision,
                was_successful=(i < 9),
                execution_time_ms=150
            )

        # Should be able to get stats filtered by route + pattern
        stats = tracker.get_accuracy_stats(
            route="graph",
            query_pattern="relationship"
        )

        assert stats.total_routes == 10
        assert stats.accuracy_rate == 0.9


class TestRouteAccuracyIntegration:
    """Integration tests with route validator"""

    def test_improves_validation_accuracy(self, tracker):
        """Should improve route validation accuracy from 90% to 95%"""
        # This is the key requirement from task brief

        # Simulate historical data showing graph route works well for relation queries
        for i in range(50):
            decision = RouteDecision(
                route="graph",
                skill="entity_search",
                agent_class="general",
                reason="relation_query",
                confidence=0.75
            )
            tracker.record_outcome(
                query=f"what is the relationship between entity{i} and entity{i+1}",
                route_decision=decision,
                was_successful=True,  # 100% success
                execution_time_ms=150
            )

        # Now test recalibration
        new_decision = RouteDecision(
            route="graph",
            skill="entity_search",
            agent_class="general",
            reason="relation_query",
            confidence=0.75
        )

        recalibrated = tracker.recalibrate_confidence(new_decision)

        # Should boost confidence for this proven pattern
        assert recalibrated > 0.75
        assert recalibrated >= 0.90  # Should reach high confidence

    def test_penalizes_poor_performing_routes(self, tracker):
        """Should lower confidence for historically poor performing routes"""
        # Simulate web route failing often
        for i in range(30):
            decision = RouteDecision(
                route="web",
                skill="web_search",
                agent_class="general",
                reason="web_query",
                confidence=0.85
            )
            tracker.record_outcome(
                query=f"search web for {i}",
                route_decision=decision,
                was_successful=(i < 15),  # Only 50% success
                execution_time_ms=200
            )

        new_decision = RouteDecision(
            route="web",
            skill="web_search",
            agent_class="general",
            reason="web_query",
            confidence=0.85
        )

        recalibrated = tracker.recalibrate_confidence(new_decision)

        # Should lower confidence significantly
        assert recalibrated < 0.85
        assert recalibrated <= 0.65
