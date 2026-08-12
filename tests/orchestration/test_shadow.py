"""Regression tests for the typed orchestration shadow runner."""

from __future__ import annotations

import ast

from app.orchestration.shadow import ShadowRollout, ShadowRunner
from app.pipeline.contracts import PipelineRequest, PipelineResult, PipelineRoute
from app.pipeline.profiles import PipelineProfile


class _ImmediateQueue:
    """Run submitted work synchronously so the comparison is deterministic."""

    def submit(self, callback):
        callback()
        return True


class _RecordingSink:
    def __init__(self) -> None:
        self.observations = []

    def record(self, observation) -> None:
        self.observations.append(observation)


class _CandidatePipeline:
    def __init__(self) -> None:
        self.requests = []

    def execute_sync(self, request):
        self.requests.append(request)
        return PipelineResult(
            answer="candidate answer",
            citations=(),
            route=PipelineRoute(route="vector"),
            quality_report={"grounding_support_ratio": 0.7},
        )


def test_shadow_returns_primary_result_and_records_candidate_difference() -> None:
    primary = PipelineResult(
        answer="primary answer",
        citations=(),
        route=PipelineRoute(route="vector"),
        quality_report={"grounding_support_ratio": 0.8},
    )
    request = PipelineRequest(question="What is RAG?", profile=PipelineProfile.STANDARD)
    sink = _RecordingSink()
    candidate = _CandidatePipeline()
    runner = ShadowRunner(
        rollout=ShadowRollout(mode="shadow", sample_percent=100, candidate_profile="baseline"),
        queue=_ImmediateQueue(),
        sink=sink,
        candidate_pipeline_factory=lambda: candidate,
    )

    returned = runner.submit(primary=primary, request=request)

    assert returned is primary
    assert candidate.requests[0].retrieval_strategy == "baseline"
    observation = sink.observations[0]
    assert observation.status == "completed"
    assert observation.answer_similarity < 1
    assert observation.primary_grounding == 0.8
    assert observation.candidate_grounding == 0.7


def test_public_query_routes_do_not_directly_import_the_legacy_run_query() -> None:
    from pathlib import Path

    routes_dir = Path("app/api/routes")
    offenders: list[Path] = []
    for path in routes_dir.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8-sig"))
        has_legacy_import = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "app.graph.workflow"
            and any(alias.name == "run_query" for alias in node.names)
            for node in ast.walk(tree)
        )
        has_legacy_call = any(
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "run_query"
            for node in ast.walk(tree)
        )
        if has_legacy_import or has_legacy_call:
            offenders.append(path)

    assert offenders == []


def test_shadow_queue_failure_cannot_replace_primary_result() -> None:
    class _BrokenQueue:
        def submit(self, _callback):
            raise RuntimeError("queue unavailable")

    primary = PipelineResult(answer="primary", citations=(), route=PipelineRoute(route="vector"))
    runner = ShadowRunner(
        rollout=ShadowRollout(mode="shadow", sample_percent=100),
        queue=_BrokenQueue(),
        sink=_RecordingSink(),
        candidate_pipeline_factory=_CandidatePipeline,
    )

    assert runner.submit(primary=primary, request=PipelineRequest(question="q", profile=PipelineProfile.STANDARD)) is primary
