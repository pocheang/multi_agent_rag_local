"""The benchmark query set must load on a fresh checkout.

``run_benchmark`` only ever read ``data/eval/benchmark_queries.txt``.  ``data/`` is
gitignored runtime state, so on any checkout where nobody hand-placed that file the
job raised ``ValueError("benchmark query set is empty")`` -- inside the background
queue, where the 202 response never surfaces it.  A tracked default under ``config/``
is what makes the endpoint work out of the box.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from app.services.runtime import runtime_ops

TRACKED_DEFAULT = Path("config/eval/benchmark_queries.txt")


@pytest.fixture
def scratch() -> Iterator[Path]:
    # Deliberately not pytest's tmp_path: its basetemp root needs directory
    # permissions that are not available on every Windows checkout.
    root = Path(tempfile.mkdtemp(prefix="querymind-benchmark-"))
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


@pytest.fixture
def no_trend_writes(monkeypatch) -> None:
    monkeypatch.setattr(runtime_ops, "append_benchmark_trend", lambda entry: None)


def _recorder(asked: list[str]):
    def execute_query(question: str) -> dict[str, Any]:
        asked.append(question)
        return {"grounding": {"support_ratio": 1.0}, "vector_result": {"citations": ["doc:1"]}}

    return execute_query


def test_tracked_default_query_set_exists_and_is_version_controlled():
    assert TRACKED_DEFAULT.exists(), "the shipped benchmark query set is missing"
    assert TRACKED_DEFAULT in runtime_ops._BENCHMARK_QUERY_PATHS


def test_comment_and_blank_lines_are_not_run_as_queries(monkeypatch, scratch, no_trend_writes):
    query_file = scratch / "queries.txt"
    query_file.write_text(
        "# a comment\n\n   \nreal question one\n#another comment\nreal question two\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(runtime_ops, "_BENCHMARK_QUERY_PATHS", (query_file,))

    asked: list[str] = []
    entry = runtime_ops.run_benchmark(max_queries=10, execute_query=_recorder(asked))

    assert asked == ["real question one", "real question two"]
    assert entry["num_queries"] == 2


def test_operator_override_wins_over_the_tracked_default(monkeypatch, scratch, no_trend_writes):
    override = scratch / "override.txt"
    override.write_text("deployment specific question\n", encoding="utf-8")
    monkeypatch.setattr(runtime_ops, "_BENCHMARK_QUERY_PATHS", (override, TRACKED_DEFAULT))

    asked: list[str] = []
    runtime_ops.run_benchmark(max_queries=10, execute_query=_recorder(asked))

    assert asked == ["deployment specific question"]


def test_shipped_default_runs_without_an_operator_override(monkeypatch, no_trend_writes):
    """What a fresh checkout actually does: no data/eval, so config/eval must carry it."""
    monkeypatch.setattr(runtime_ops, "_BENCHMARK_QUERY_PATHS", (Path("data/eval/does-not-exist.txt"), TRACKED_DEFAULT))

    asked: list[str] = []
    entry = runtime_ops.run_benchmark(max_queries=30, execute_query=_recorder(asked))

    assert entry["num_queries"] > 0
    assert not any(question.startswith("#") for question in asked), asked


def test_missing_query_set_still_raises(monkeypatch, scratch):
    monkeypatch.setattr(runtime_ops, "_BENCHMARK_QUERY_PATHS", (scratch / "nope.txt",))

    with pytest.raises(ValueError, match="benchmark query set is empty"):
        runtime_ops.run_benchmark(max_queries=5, execute_query=lambda q: {})
