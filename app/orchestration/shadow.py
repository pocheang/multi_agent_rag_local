"""Typed shadow execution for observing a candidate orchestration profile."""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, Protocol, Self, TypeGuard

from pydantic import Field

from app.domain.contracts import ImmutableContract
from app.orchestration.request import OrchestrationRequest
from app.services.consistency_guard import text_similarity
from app.services.runtime.runtime_ops import append_shadow_run

_DEFAULT_ROLLOUT_PATH = Path(__file__).resolve().parents[2] / "config" / "orchestration_rollout.json"


class ObservationGate(ImmutableContract):
    """Explicit evidence requirements before legacy adapters may be removed."""

    minimum_samples: int = Field(default=500, ge=0)
    minimum_days: int = Field(default=14, ge=0)
    min_answer_similarity: float = Field(default=0.95, ge=0, le=1)
    max_failure_rate: float = Field(default=0.05, ge=0, le=1)


class ShadowRollout(ImmutableContract):
    """A bounded candidate rollout policy loaded from deployment configuration."""

    mode: Literal["disabled", "shadow", "new"] = "disabled"
    sample_percent: int = Field(default=0, ge=0, le=100)
    candidate_profile: str = Field(default="baseline", min_length=1)
    seed: str = Field(default="orchestration-shadow", min_length=1)
    observation: ObservationGate = Field(default_factory=ObservationGate)


class ShadowObservation(ImmutableContract):
    """Safe aggregate data captured for one candidate comparison."""

    status: Literal["completed", "failed", "skipped"]
    candidate_profile: str
    latency_ms: float = Field(default=0, ge=0)
    answer_similarity: float | None = Field(default=None, ge=0, le=1)
    primary_grounding: float = Field(default=0, ge=0, le=1)
    candidate_grounding: float = Field(default=0, ge=0, le=1)
    primary_citation_count: int = Field(default=0, ge=0)
    candidate_citation_count: int = Field(default=0, ge=0)
    error_type: str | None = None
    observed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ShadowQueue(Protocol):
    """Minimal queue boundary used to avoid adding latency to primary requests."""

    def submit(self, callback: Callable[[], None]) -> bool:
        """Schedule a callback and report whether it was accepted."""


class ShadowObservationSink(Protocol):
    """Persistence boundary for already-sanitized observation data."""

    def record(self, observation: ShadowObservation) -> None:
        """Persist one observation without retaining raw user content."""


class CandidatePipeline(Protocol):
    """Runtime boundary for a candidate pipeline without a pipeline import."""

    def execute_sync(self, request: object) -> object:
        """Execute one candidate request."""


class PipelineResultLike(Protocol):
    """Fields required to compare an already-normalized candidate result."""

    answer: str
    citations: object
    quality_report: dict[str, object]


class ShadowActor(Protocol):
    """Minimal identity shape used for deterministic shadow sampling."""

    user_id: str | None


class ShadowRequest(Protocol):
    """Orchestration-owned request view for shadow selection and cloning."""

    question: str
    session_id: str | None
    actor: ShadowActor | None

    def model_copy(self, *, update: dict[str, object] | None = None) -> Self:
        """Return a copy with the candidate profile override applied."""


class RuntimeShadowObservationSink:
    """Adapt typed observations to the existing JSONL operations log."""

    def record(self, observation: ShadowObservation) -> None:
        append_shadow_run(observation.model_dump(mode="json"))


def load_shadow_rollout(path: Path = _DEFAULT_ROLLOUT_PATH) -> ShadowRollout:
    """Load the deployment policy, failing closed when it is absent or invalid."""
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return ShadowRollout.model_validate(payload)
    except (OSError, json.JSONDecodeError, ValueError):
        return ShadowRollout()


def _grounding(result: PipelineResultLike) -> float:
    value = result.quality_report.get("grounding_support_ratio", result.quality_report.get("support_ratio", 0.0))
    return float(value) if isinstance(value, int | float) else 0.0


class ShadowRunner:
    """Return the primary answer while asynchronously comparing one candidate."""

    def __init__(
        self,
        *,
        rollout: ShadowRollout,
        queue: ShadowQueue,
        sink: ShadowObservationSink,
        candidate_pipeline_factory: Callable[[], CandidatePipeline],
    ) -> None:
        self._rollout = rollout
        self._queue = queue
        self._sink = sink
        self._candidate_pipeline_factory = candidate_pipeline_factory

    def submit(self, *, primary: PipelineResultLike, request: ShadowRequest) -> PipelineResultLike:
        """Schedule a candidate run when selected, always returning ``primary``."""
        if not self._is_selected(request):
            return primary

        candidate_request = request.model_copy(
            update={"retrieval_strategy": self._rollout.candidate_profile}
        )

        def compare() -> None:
            started = time.perf_counter()
            try:
                candidate = self._candidate_pipeline_factory().execute_sync(candidate_request)
                if not _is_pipeline_result(candidate):
                    raise TypeError("candidate pipeline returned an unsupported result")
            except Exception as exc:
                self._record(
                    ShadowObservation(
                        status="failed",
                        candidate_profile=self._rollout.candidate_profile,
                        error_type=type(exc).__name__,
                    )
                )
                return
            self._record(
                ShadowObservation(
                    status="completed",
                    candidate_profile=self._rollout.candidate_profile,
                    latency_ms=round((time.perf_counter() - started) * 1000, 2),
                    answer_similarity=round(text_similarity(primary.answer, candidate.answer), 4),
                    primary_grounding=_grounding(primary),
                    candidate_grounding=_grounding(candidate),
                    primary_citation_count=len(primary.citations),
                    candidate_citation_count=len(candidate.citations),
                )
            )

        try:
            accepted = self._queue.submit(compare)
        except Exception as exc:
            self._record(
                ShadowObservation(
                    status="failed",
                    candidate_profile=self._rollout.candidate_profile,
                    error_type=type(exc).__name__,
                )
            )
            return primary
        if not accepted:
            self._record(
                ShadowObservation(
                    status="skipped",
                    candidate_profile=self._rollout.candidate_profile,
                    error_type="queue_full",
                )
            )
        return primary

    def _record(self, observation: ShadowObservation) -> None:
        """Keep telemetry failures isolated from the primary request."""
        try:
            self._sink.record(observation)
        except Exception:
            return

    def _is_selected(self, request: ShadowRequest | OrchestrationRequest) -> bool:
        if self._rollout.mode != "shadow" or self._rollout.sample_percent == 0:
            return False
        user_id = request.actor.user_id if request.actor and request.actor.user_id else ""
        key = f"{self._rollout.seed}|{user_id}|{request.session_id or ''}|{request.question}"
        bucket = int(hashlib.sha256(key.encode("utf-8")).hexdigest()[:8], 16) % 100
        return bucket < self._rollout.sample_percent


def _is_pipeline_result(value: object) -> TypeGuard[PipelineResultLike]:
    """Validate the structural result contract without importing pipeline modules."""
    return all(hasattr(value, attribute) for attribute in ("answer", "citations", "quality_report"))


__all__ = [
    "ObservationGate",
    "RuntimeShadowObservationSink",
    "ShadowObservation",
    "ShadowRollout",
    "ShadowRunner",
    "ShadowRequest",
    "load_shadow_rollout",
]
