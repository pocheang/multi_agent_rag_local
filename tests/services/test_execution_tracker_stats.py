"""What the two agent-statistics endpoints count, and where they disagree.

`get_quality_stats` (51), `get_execution_stats` (36) and `track_agent_execution`
(27) were three `python:S3776` findings in one file until 2026-09-06. The split
into accumulator helpers was verified byte-for-byte against the old
implementation over a fixture reaching every branch, so these tests are not about
that. They pin the four behaviours that are surprising enough to be "tidied" into
a bug by someone reading the helpers without the history.

The first is the important one: **the two endpoints label the same error
differently**, and always have. `/admin/agent-quality` clamps an error type to
fifty characters and answers "Unknown" for an empty message; the health endpoint's
`get_execution_stats` does neither. Unifying them is a defensible change with a
visible consequence -- the quality dashboard would regroup -- and not something to
do as a side effect of a complexity refactor.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.services.observability import agent_execution_tracker as tracker_module
from app.services.observability.agent_execution_tracker import (
    AgentExecutionTracker,
    AgentStep,
    ExecutionTrace,
)

_NOW = datetime(2026, 9, 6, 12, 0, 0, tzinfo=UTC)


def _step(agent: str, status: str = "completed", **kw) -> AgentStep:
    return AgentStep(agent_name=agent, status=status, **kw)


@pytest.fixture
def tracker(monkeypatch):
    """A tracker with a frozen clock, so the one-hour 'active' window is stable."""
    monkeypatch.setattr(tracker_module, "utcnow", lambda: _NOW)
    instance = AgentExecutionTracker()
    instance._traces = {}
    return instance


def _load(tracker: AgentExecutionTracker, *steps: AgentStep) -> None:
    tracker._traces["t"] = ExecutionTrace(execution_id="t", query="q", steps=list(steps))


def test_the_two_endpoints_label_the_same_error_differently(tracker):
    long_type = "E" * 80
    _load(
        tracker,
        _step("a", "failed", error=f"{long_type}: detail"),
        _step("a", "failed", error=""),
    )

    execution = tracker.get_execution_stats()["a"]["error_types"]
    quality = tracker.get_quality_stats()["error_distribution"]

    # get_execution_stats: no length clamp, and an empty message becomes "unknown".
    assert set(execution) == {long_type, "unknown"}
    # get_quality_stats: clamped to fifty characters. The empty message is passed
    # in as the literal "unknown", so it does *not* reach the "Unknown" branch --
    # that branch is only reachable by calling _extract_error_type directly.
    assert set(quality) == {"E" * 50, "unknown"}

    assert AgentExecutionTracker._extract_error_type("") == "Unknown"


def test_a_step_with_no_duration_does_not_dilute_the_average(tracker):
    # Three executions, one timed. avg_response_time divides by the timed one,
    # not by three -- `timed_steps` and `executions` are separate counters and
    # collapsing them would quietly divide every response time by the wrong number.
    _load(
        tracker,
        _step("a", duration_ms=3000.0, end_time=_NOW),
        _step("a", end_time=_NOW),
        _step("a", status="running"),
    )

    summary = tracker.get_quality_stats()["summary"]
    assert summary["total_executions"] == 3
    assert summary["avg_response_time"] == pytest.approx(3.0)


def test_a_step_that_has_not_finished_is_in_no_timeline_bucket(tracker):
    _load(
        tracker,
        _step("a", end_time=datetime(2026, 9, 6, 11, 30, 0, tzinfo=UTC)),
        _step("a", "failed", error="x", end_time=datetime(2026, 9, 6, 11, 30, 59, tzinfo=UTC)),
        _step("a", status="running"),
    )

    timeline = tracker.get_quality_stats()["timeline"]
    # Both finished steps fall in the same minute; the running one is absent.
    assert timeline == [{"timestamp": "2026-09-06T11:30:00", "success": 1, "failure": 1}]


def test_an_empty_tracker_reports_a_perfect_rate_rather_than_zero(tracker):
    summary = tracker.get_quality_stats()["summary"]
    assert summary["total_executions"] == 0
    # 1.0, not 0.0: nothing has failed. A dashboard showing 0% success for a quiet
    # system is the "average over no samples" defect this repository records for
    # the grounding SLO.
    assert summary["overall_success_rate"] == 1.0
    assert summary["active_agents"] == 0
    assert tracker.get_execution_stats() == {}


def test_working_fields_never_reach_the_caller(tracker):
    _load(tracker, _step("a", duration_ms=10.0, end_time=_NOW, metadata={"tokens": 7}))

    working = {"total_duration_ms", "total_tokens", "token_count"}
    assert not working & set(tracker.get_execution_stats()["a"])
    assert not working & set(tracker.get_quality_stats()["agents"][0])


def test_only_a_recently_finished_agent_counts_as_active(tracker):
    _load(
        tracker,
        _step("recent", end_time=datetime(2026, 9, 6, 11, 30, 0, tzinfo=UTC)),
        _step("stale", end_time=datetime(2026, 9, 6, 10, 0, 0, tzinfo=UTC)),
        _step("never", status="running"),
    )

    assert tracker.get_quality_stats()["summary"]["active_agents"] == 1
