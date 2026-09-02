"""Confidence bucketing, and the two things that were said with float equality.

Both spellings worked for the table as it stands and neither said what it meant,
which is why `python:S1244` found them and why replacing them with
`math.isclose` would have been the wrong repair -- the values compared are exact
binary fractions, so precision was never the problem. The problem was that each
comparison encoded a fact about the *current* table into code that is supposed to
work from it.

- `confidence == 1.0 and high == 1.0` meant "this is the last bucket, whose upper
  bound has to be inclusive". Said that way it holds only while the table ends at
  1.0; the moment it does not, the clamped maximum matches no bucket and falls
  through to a fallback that returns the *lowest* one.
- `bucket.low == 0.5 and bucket.high == 1.0` meant "these boundaries were absent
  from the file, so fill them in" -- a guess that cannot tell an absent boundary
  from a genuine one, and needed a special case for the first bucket to cover for
  that. Boundaries are a property of the scheme, and the bucket's own name already
  encodes them, so they are now taken from the table outright.

The first two tests pin today's behaviour, unchanged. The last two pin the
reason the rewrite was worth doing.
"""

from __future__ import annotations

import pytest

from app.agents.router import calibration
from app.agents.router.calibration import (
    CONFIDENCE_BUCKETS,
    CalibrationBucket,
    CalibrationData,
    get_bucket_for_confidence,
)


class TestBucketingIsUnchanged:
    @pytest.mark.parametrize(
        ("confidence", "expected"),
        [
            (0.5, "0.5-0.6"),
            (0.55, "0.5-0.6"),
            (0.6, "0.6-0.7"),
            (0.9, "0.9-1.0"),
            (0.999, "0.9-1.0"),
            (1.0, "0.9-1.0"),
        ],
    )
    def test_each_confidence_lands_where_it_did(self, confidence: float, expected: str) -> None:
        assert get_bucket_for_confidence(confidence) == expected

    @pytest.mark.parametrize(("confidence", "expected"), [(1.5, "0.9-1.0"), (0.1, "0.5-0.6"), (-3.0, "0.5-0.6")])
    def test_values_outside_the_range_are_clamped_into_it(self, confidence: float, expected: str) -> None:
        assert get_bucket_for_confidence(confidence) == expected

    def test_every_bucket_in_the_table_is_reachable(self) -> None:
        """A gap would show up here rather than as a quietly mis-filed prediction."""

        reached = {get_bucket_for_confidence((low + high) / 2) for low, high in CONFIDENCE_BUCKETS}

        assert reached == {f"{low}-{high}" for low, high in CONFIDENCE_BUCKETS}


class TestTheTopBucketIsInclusiveByPositionNotByValue:
    def test_a_table_that_does_not_end_at_one_still_works(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The failure the old spelling would have had: the top value falling to
        the bottom bucket, which is not a near-miss but the opposite answer."""

        monkeypatch.setattr(calibration, "CONFIDENCE_BUCKETS", [(0.0, 0.5), (0.5, 0.95)])

        assert get_bucket_for_confidence(0.95) == "0.5-0.95"
        assert get_bucket_for_confidence(99.0) == "0.5-0.95"


class TestBoundariesComeFromTheTable:
    def test_a_persisted_boundary_that_disagrees_with_the_name_is_corrected(self) -> None:
        """It could only ever have been wrong: the key encodes the true pair."""

        restored = CalibrationData.from_dict(
            {"buckets": {"0.7-0.8": {"total_predictions": 9, "correct_predictions": 4, "low": 0.5, "high": 1.0}}}
        )

        bucket = restored.buckets["0.7-0.8"]
        assert (bucket.low, bucket.high) == (0.7, 0.8)
        assert bucket.total_predictions == 9, "the accumulated data must survive the correction"

    def test_the_first_bucket_gets_the_same_treatment(self) -> None:
        """The old code exempted it by name, because its guess could not tell a
        default boundary from a real one."""

        restored = CalibrationData.from_dict({"buckets": {"0.5-0.6": CalibrationBucket().to_dict()}})

        assert (restored.buckets["0.5-0.6"].low, restored.buckets["0.5-0.6"].high) == (0.5, 0.6)

    def test_missing_buckets_are_created_from_the_table(self) -> None:
        restored = CalibrationData.from_dict({"buckets": {}})

        assert set(restored.buckets) == {f"{low}-{high}" for low, high in CONFIDENCE_BUCKETS}
