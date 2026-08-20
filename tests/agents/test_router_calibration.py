"""
Tests for router confidence calibration system.

Tests calibration logic that adjusts raw confidence scores
to better reflect actual routing accuracy.
"""

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.agents.router.calibration import (
    CalibrationBucket,
    CalibrationData,
    ConfidenceCalibrator,
    apply_calibration,
    get_bucket_for_confidence,
    load_calibration_data,
    save_calibration_data,
    update_calibration_data,
)


class TestCalibrationBuckets:
    """Test confidence bucket assignment."""

    def test_get_bucket_for_confidence_boundaries(self):
        """Test bucket assignment at boundaries."""
        assert get_bucket_for_confidence(0.5) == "0.5-0.6"
        assert get_bucket_for_confidence(0.6) == "0.6-0.7"
        assert get_bucket_for_confidence(0.7) == "0.7-0.8"
        assert get_bucket_for_confidence(0.8) == "0.8-0.9"
        assert get_bucket_for_confidence(0.9) == "0.9-1.0"
        assert get_bucket_for_confidence(1.0) == "0.9-1.0"

    def test_get_bucket_for_confidence_midpoints(self):
        """Test bucket assignment at midpoints."""
        assert get_bucket_for_confidence(0.55) == "0.5-0.6"
        assert get_bucket_for_confidence(0.65) == "0.6-0.7"
        assert get_bucket_for_confidence(0.75) == "0.7-0.8"
        assert get_bucket_for_confidence(0.85) == "0.8-0.9"
        assert get_bucket_for_confidence(0.95) == "0.9-1.0"

    def test_get_bucket_for_confidence_edge_cases(self):
        """Test bucket assignment for edge cases."""
        # Below minimum - should clamp to lowest bucket
        assert get_bucket_for_confidence(0.3) == "0.5-0.6"
        assert get_bucket_for_confidence(0.0) == "0.5-0.6"

        # Above maximum - should use highest bucket
        assert get_bucket_for_confidence(1.1) == "0.9-1.0"


class TestCalibrationData:
    """Test calibration data structure."""

    def test_calibration_bucket_initial_state(self):
        """Test initial state of calibration bucket."""
        bucket = CalibrationBucket()
        assert bucket.total_predictions == 0
        assert bucket.correct_predictions == 0
        assert bucket.historical_accuracy == 0.5  # Default
        assert bucket.last_updated is None

    def test_calibration_bucket_accuracy_calculation(self):
        """Test accuracy calculation."""
        bucket = CalibrationBucket(total_predictions=10, correct_predictions=7)
        assert bucket.historical_accuracy == 0.7

    def test_calibration_bucket_no_predictions(self):
        """Test accuracy when no predictions."""
        bucket = CalibrationBucket(total_predictions=0, correct_predictions=0)
        assert bucket.historical_accuracy == 0.5  # Default fallback

    def test_calibration_data_initialization(self):
        """Test calibration data initialization."""
        data = CalibrationData()
        assert len(data.buckets) == 5
        assert "0.5-0.6" in data.buckets
        assert "0.9-1.0" in data.buckets
        assert data.version == "1.0"

    def test_calibration_data_serialization(self):
        """Test serialization to dict."""
        data = CalibrationData()
        data.buckets["0.7-0.8"].total_predictions = 10
        data.buckets["0.7-0.8"].correct_predictions = 8

        result = data.to_dict()
        assert result["version"] == "1.0"
        assert "0.7-0.8" in result["buckets"]
        assert result["buckets"]["0.7-0.8"]["total_predictions"] == 10
        assert result["buckets"]["0.7-0.8"]["correct_predictions"] == 8

    def test_calibration_data_deserialization(self):
        """Test deserialization from dict."""
        data_dict = {
            "version": "1.0",
            "buckets": {
                "0.7-0.8": {
                    "total_predictions": 15,
                    "correct_predictions": 12,
                    "last_updated": "2026-06-27T10:00:00"
                }
            }
        }

        data = CalibrationData.from_dict(data_dict)
        assert data.version == "1.0"
        assert data.buckets["0.7-0.8"].total_predictions == 15
        assert data.buckets["0.7-0.8"].correct_predictions == 12


class TestCalibrationPersistence:
    """Test saving and loading calibration data."""

    def test_save_and_load_calibration_data(self):
        """Test round-trip save and load."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "calibration.json"

            # Create and save data
            data = CalibrationData()
            data.buckets["0.8-0.9"].total_predictions = 20
            data.buckets["0.8-0.9"].correct_predictions = 18

            save_calibration_data(data, config_path)

            # Load and verify
            loaded_data = load_calibration_data(config_path)
            assert loaded_data.buckets["0.8-0.9"].total_predictions == 20
            assert loaded_data.buckets["0.8-0.9"].correct_predictions == 18

    def test_load_nonexistent_file(self):
        """Test loading when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nonexistent.json"

            data = load_calibration_data(config_path)
            assert isinstance(data, CalibrationData)
            assert data.buckets["0.5-0.6"].total_predictions == 0

    def test_load_corrupted_file(self):
        """Test loading corrupted JSON file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "corrupted.json"
            config_path.write_text("{ invalid json }")

            data = load_calibration_data(config_path)
            assert isinstance(data, CalibrationData)  # Should return default


class TestCalibrationUpdates:
    """Test updating calibration data with feedback."""

    def test_update_calibration_data_correct(self):
        """Test updating with correct prediction."""
        data = CalibrationData()

        update_calibration_data(data, raw_confidence=0.75, was_correct=True)

        bucket = data.buckets["0.7-0.8"]
        assert bucket.total_predictions == 1
        assert bucket.correct_predictions == 1
        assert bucket.historical_accuracy == 1.0

    def test_update_calibration_data_incorrect(self):
        """Test updating with incorrect prediction."""
        data = CalibrationData()

        update_calibration_data(data, raw_confidence=0.85, was_correct=False)

        bucket = data.buckets["0.8-0.9"]
        assert bucket.total_predictions == 1
        assert bucket.correct_predictions == 0
        assert bucket.historical_accuracy == 0.0

    def test_update_calibration_data_multiple(self):
        """Test multiple updates to same bucket."""
        data = CalibrationData()

        update_calibration_data(data, raw_confidence=0.92, was_correct=True)
        update_calibration_data(data, raw_confidence=0.95, was_correct=True)
        update_calibration_data(data, raw_confidence=0.91, was_correct=False)

        bucket = data.buckets["0.9-1.0"]
        assert bucket.total_predictions == 3
        assert bucket.correct_predictions == 2
        assert abs(bucket.historical_accuracy - 0.667) < 0.01


class TestConfidenceCalibration:
    """Test confidence calibration logic."""

    def test_apply_calibration_no_history(self):
        """Test calibration with no historical data."""
        data = CalibrationData()

        calibrated = apply_calibration(0.75, data)

        # Should return raw confidence when no history
        assert calibrated == 0.75

    def test_apply_calibration_with_history(self):
        """Test calibration with historical data."""
        data = CalibrationData()
        data.buckets["0.7-0.8"].total_predictions = 10
        data.buckets["0.7-0.8"].correct_predictions = 6  # 60% accuracy

        calibrated = apply_calibration(0.75, data)

        # New formula: 0.75 * (0.6 / 0.75) = 0.6
        assert abs(calibrated - 0.6) < 0.01

    def test_apply_calibration_overconfident(self):
        """Test calibration reduces overconfidence."""
        data = CalibrationData()
        data.buckets["0.9-1.0"].total_predictions = 20
        data.buckets["0.9-1.0"].correct_predictions = 14  # 70% accuracy

        calibrated = apply_calibration(0.95, data)

        # New formula: 0.95 * (0.7 / 0.95) ≈ 0.7
        assert calibrated < 0.95
        assert abs(calibrated - 0.7) < 0.01

    def test_apply_calibration_underconfident(self):
        """Test calibration increases underconfidence."""
        data = CalibrationData()
        data.buckets["0.5-0.6"].total_predictions = 15
        data.buckets["0.5-0.6"].correct_predictions = 12  # 80% accuracy

        calibrated = apply_calibration(0.55, data)

        # New formula: 0.55 * (0.8 / 0.55) ≈ 0.8
        assert calibrated > 0.55
        assert abs(calibrated - 0.8) < 0.01

    def test_apply_calibration_clamps_to_range(self):
        """Test calibration clamps to [0.0, 1.0]."""
        data = CalibrationData()
        data.buckets["0.9-1.0"].total_predictions = 5
        data.buckets["0.9-1.0"].correct_predictions = 5  # 100% accuracy

        # Even with perfect accuracy, shouldn't exceed 1.0
        calibrated = apply_calibration(0.95, data)
        assert 0.0 <= calibrated <= 1.0

    def test_apply_calibration_minimum_samples(self):
        """Test calibration requires minimum samples."""
        data = CalibrationData()
        data.buckets["0.8-0.9"].total_predictions = 2  # Below threshold
        data.buckets["0.8-0.9"].correct_predictions = 1

        calibrated = apply_calibration(0.85, data)

        # Should return raw confidence (not enough samples)
        assert calibrated == 0.85


class TestConfidenceCalibrator:
    """Test ConfidenceCalibrator class."""

    def test_calibrator_initialization_default(self):
        """Test calibrator with default config."""
        calibrator = ConfidenceCalibrator()
        assert calibrator.calibration_data is not None
        assert calibrator.config_path is not None

    def test_calibrator_initialization_custom_path(self):
        """Test calibrator with custom config path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "custom.json"
            calibrator = ConfidenceCalibrator(config_path=config_path)
            assert calibrator.config_path == config_path

    def test_calibrator_calibrate(self):
        """Test calibrate method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "calibration.json"
            calibrator = ConfidenceCalibrator(config_path=config_path)

            # Add some history
            calibrator.calibration_data.buckets["0.7-0.8"].total_predictions = 10
            calibrator.calibration_data.buckets["0.7-0.8"].correct_predictions = 8

            calibrated = calibrator.calibrate(0.75)

            # New formula: 0.75 * (0.8 / 0.75) = 0.8
            assert calibrated != 0.75
            assert abs(calibrated - 0.8) < 0.01

    def test_calibrator_record_feedback(self):
        """Test record_feedback method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "calibration.json"
            calibrator = ConfidenceCalibrator(config_path=config_path)

            calibrator.record_feedback(raw_confidence=0.65, was_correct=True)

            bucket = calibrator.calibration_data.buckets["0.6-0.7"]
            assert bucket.total_predictions == 1
            assert bucket.correct_predictions == 1

    def test_calibrator_saves_on_feedback(self):
        """Test that feedback triggers save."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "calibration.json"
            calibrator = ConfidenceCalibrator(config_path=config_path)

            calibrator.record_feedback(raw_confidence=0.85, was_correct=True)

            # Reload and verify persistence
            new_calibrator = ConfidenceCalibrator(config_path=config_path)
            bucket = new_calibrator.calibration_data.buckets["0.8-0.9"]
            assert bucket.total_predictions == 1

    def test_calibrator_get_stats(self):
        """Test get_stats method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "calibration.json"
            calibrator = ConfidenceCalibrator(config_path=config_path)

            # Add some data
            calibrator.record_feedback(0.75, True)
            calibrator.record_feedback(0.85, False)

            stats = calibrator.get_stats()
            assert "0.7-0.8" in stats
            assert "0.8-0.9" in stats
            assert stats["0.7-0.8"]["total_predictions"] == 1
            assert stats["0.8-0.9"]["total_predictions"] == 1


class TestCalibrationIntegration:
    """Integration tests for calibration system."""

    def test_full_calibration_workflow(self):
        """Test complete calibration workflow."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "calibration.json"
            calibrator = ConfidenceCalibrator(config_path=config_path)

            # Initial prediction (no history)
            calibrated_1 = calibrator.calibrate(0.9)
            assert calibrated_1 == 0.9  # No adjustment yet

            # Record that prediction was wrong
            calibrator.record_feedback(0.9, was_correct=False)

            # Add more feedback
            for _ in range(4):
                calibrator.record_feedback(0.92, was_correct=False)

            # Now calibration should reduce confidence
            calibrated_2 = calibrator.calibrate(0.9)
            assert calibrated_2 < 0.9  # Should be reduced

            # Verify stats
            stats = calibrator.get_stats()
            assert stats["0.9-1.0"]["total_predictions"] == 5
            assert stats["0.9-1.0"]["correct_predictions"] == 0

    def test_calibration_improves_over_time(self):
        """Test that calibration improves with more data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "calibration.json"
            calibrator = ConfidenceCalibrator(config_path=config_path)

            # Simulate overconfident predictions
            for i in range(20):
                calibrator.record_feedback(
                    raw_confidence=0.85,
                    was_correct=(i % 2 == 0)  # 50% accuracy
                )

            # Calibration should now reflect the actual accuracy
            calibrated = calibrator.calibrate(0.85)

            # Should be close to 0.5 (actual accuracy)
            assert abs(calibrated - 0.5) < 0.1

    def test_different_buckets_calibrated_independently(self):
        """Test that different confidence buckets are calibrated independently."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "calibration.json"
            calibrator = ConfidenceCalibrator(config_path=config_path)

            # Low confidence bucket: accurate
            for _ in range(10):
                calibrator.record_feedback(0.55, was_correct=True)

            # High confidence bucket: inaccurate
            for _ in range(10):
                calibrator.record_feedback(0.95, was_correct=False)

            # Low confidence should increase
            calibrated_low = calibrator.calibrate(0.55)
            assert calibrated_low > 0.55

            # High confidence should decrease
            calibrated_high = calibrator.calibrate(0.95)
            assert calibrated_high < 0.95
