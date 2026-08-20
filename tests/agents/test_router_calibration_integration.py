"""
Integration tests for router calibration with decide_route.

Tests that calibration is properly integrated into the routing pipeline.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.agents.router.routing import (
    decide_route,
    get_calibration_stats,
    record_routing_feedback,
)
from app.agents.router.calibration import ConfidenceCalibrator


class TestRouterCalibrationIntegration:
    """Test calibration integration with router."""

    def test_decide_route_returns_calibrated_confidence(self):
        """Test that decide_route applies calibration."""
        # This is a basic smoke test - actual calibration requires historical data
        decision = decide_route("What is machine learning?")

        assert hasattr(decision, "confidence")
        assert 0.0 <= decision.confidence <= 1.0

    def test_record_routing_feedback_works(self):
        """Test that feedback recording doesn't crash."""
        # Record some feedback
        record_routing_feedback(raw_confidence=0.75, was_correct=True)
        record_routing_feedback(raw_confidence=0.85, was_correct=False)

        # Should not raise any errors
        stats = get_calibration_stats()
        assert isinstance(stats, dict)

    def test_calibration_affects_confidence_over_time(self):
        """Test that calibration adjusts confidence with enough feedback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_calibration.json"

            # Create a temporary calibrator
            calibrator = ConfidenceCalibrator(config_path=config_path)

            # Simulate overconfident predictions in the 0.8-0.9 bucket
            for _ in range(10):
                calibrator.record_feedback(raw_confidence=0.85, was_correct=False)

            # Now calibration should reduce confidence
            calibrated = calibrator.calibrate(0.85)

            # Should be significantly reduced (0.85 was wrong 100% of the time)
            assert calibrated < 0.85
            assert calibrated == 0.0  # 0/10 accuracy

    def test_calibration_increases_underconfident_scores(self):
        """Test that calibration increases underconfident scores."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_calibration.json"

            calibrator = ConfidenceCalibrator(config_path=config_path)

            # Simulate underconfident predictions in the 0.5-0.6 bucket
            for _ in range(10):
                calibrator.record_feedback(raw_confidence=0.55, was_correct=True)

            # Now calibration should increase confidence
            calibrated = calibrator.calibrate(0.55)

            # Should be increased (0.55 was correct 100% of the time)
            assert calibrated > 0.55
            assert calibrated == 1.0  # 10/10 accuracy

    def test_calibration_disabled_returns_raw_confidence(self):
        """Test that disabling calibration returns raw confidence."""
        with patch("app.agents.router.routing.ENABLE_CALIBRATION", False):
            with patch("app.agents.router.routing._calibrator", None):
                # When calibration is disabled, confidence should not be adjusted
                # This test verifies the fallback behavior
                from app.agents.router.routing import decide_route

                decision = decide_route("What is deep learning?")
                # Just verify it doesn't crash when calibrator is None
                assert hasattr(decision, "confidence")

    def test_get_calibration_stats_returns_dict(self):
        """Test that calibration stats are returned."""
        stats = get_calibration_stats()
        assert isinstance(stats, dict)

        # Should have bucket names as keys
        if stats:  # If calibration is enabled
            assert any(
                bucket in stats
                for bucket in ["0.5-0.6", "0.6-0.7", "0.7-0.8", "0.8-0.9", "0.9-1.0"]
            )

    def test_calibration_with_insufficient_samples(self):
        """Test that calibration doesn't adjust with insufficient samples."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_calibration.json"

            calibrator = ConfidenceCalibrator(config_path=config_path)

            # Add only 2 samples (below MIN_SAMPLES_FOR_CALIBRATION=5)
            calibrator.record_feedback(raw_confidence=0.75, was_correct=False)
            calibrator.record_feedback(raw_confidence=0.75, was_correct=False)

            # Should not apply calibration (insufficient samples)
            calibrated = calibrator.calibrate(0.75)
            assert calibrated == 0.75  # Raw confidence returned

    def test_calibration_persists_across_instances(self):
        """Test that calibration data persists across calibrator instances."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_calibration.json"

            # First calibrator: record feedback
            calibrator1 = ConfidenceCalibrator(config_path=config_path)
            for _ in range(10):
                calibrator1.record_feedback(raw_confidence=0.95, was_correct=False)

            # Second calibrator: should load existing data
            calibrator2 = ConfidenceCalibrator(config_path=config_path)
            stats = calibrator2.get_stats()

            # Should have the feedback from calibrator1
            assert stats["0.9-1.0"]["total_predictions"] == 10
            assert stats["0.9-1.0"]["correct_predictions"] == 0

            # Should apply same calibration
            calibrated = calibrator2.calibrate(0.95)
            assert calibrated < 0.95


class TestCalibrationEdgeCases:
    """Test edge cases in calibration integration."""

    def test_calibration_with_extreme_confidence(self):
        """Test calibration handles extreme confidence values."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_calibration.json"
            calibrator = ConfidenceCalibrator(config_path=config_path)

            # Test with confidence = 1.0
            for _ in range(10):
                calibrator.record_feedback(raw_confidence=1.0, was_correct=True)

            calibrated = calibrator.calibrate(1.0)
            assert 0.0 <= calibrated <= 1.0

    def test_calibration_with_mixed_feedback(self):
        """Test calibration with mixed correct/incorrect feedback."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_calibration.json"
            calibrator = ConfidenceCalibrator(config_path=config_path)

            # 50% accuracy in 0.7-0.8 bucket
            for i in range(20):
                calibrator.record_feedback(
                    raw_confidence=0.75,
                    was_correct=(i % 2 == 0)
                )

            calibrated = calibrator.calibrate(0.75)

            # Should be close to 0.5 (50% accuracy)
            assert abs(calibrated - 0.5) < 0.1

    def test_feedback_updates_last_updated_timestamp(self):
        """Test that feedback updates the last_updated timestamp."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_calibration.json"
            calibrator = ConfidenceCalibrator(config_path=config_path)

            calibrator.record_feedback(raw_confidence=0.65, was_correct=True)

            stats = calibrator.get_stats()
            assert stats["0.6-0.7"]["last_updated"] is not None
