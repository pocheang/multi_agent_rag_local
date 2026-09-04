"""
Timeout management and execution budget control.

Provides centralized timeout enforcement across all orchestration stages
to prevent indefinite blocking and ensure predictable latency.
"""

from __future__ import annotations

import asyncio
import builtins
import time
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.domain.errors import StageExecutionError


@dataclass
class TimeoutConfig:
    """Timeout configuration for orchestration stages.

    All timeouts in milliseconds.  These are ceilings on a *hang*, not latency
    targets: the P95 target is single-digit seconds (CLAUDE.md, "Quality
    Metrics"), and a ceiling set near the target fires on ordinary traffic.  The
    defaults below mirror ``Settings.stage_timeout_*``; ``from_settings`` is the
    path production uses, so a deployment retunes them without a code change.
    """

    # Overall orchestration timeout
    total_timeout_ms: int = 120_000
    """Maximum time for entire orchestration execution.
    WHY: Prevent requests from hanging indefinitely."""

    # Per-stage timeouts
    route_timeout_ms: int = 8_000
    """Router decision timeout.
    WHY: One route decision can be three LLM calls -- intent classification, the
    route prompt, and the low-confidence reasoning retry. The old 2s ceiling did
    not cover one of them."""

    plan_timeout_ms: int = 5_000
    """Query decomposition timeout.
    WHY: Planning is optional, and its LLM decomposer only runs on opt-in."""

    retrieval_timeout_ms: int = 15_000
    """Retrieval stage timeout (all retrievers combined).
    WHY: Embedding, vector, BM25, optional graph and web, then reranking. Must
    stay above Settings.knowledge_source_timeout_ms, which bounds one source."""

    tool_timeout_ms: int = 10_000
    """Tool execution timeout.
    WHY: External tool calls may be slow (web search, API calls)."""

    synthesis_timeout_ms: int = 30_000
    """Answer synthesis timeout.
    WHY: A cited multi-paragraph answer over a full evidence context routinely
    takes longer than the old 5s ceiling, which made a timeout the normal case."""

    finalization_timeout_ms: int = 8_000
    """Validation, verification, and finalization timeout.
    WHY: The validation cascade can reach NLI and an LLM deep-validation level."""

    # Buffer for overhead
    overhead_buffer_ms: int = 2_000
    """Buffer for orchestration overhead (event publishing, type conversions).
    WHY: Sum of stage timeouts should not exceed total timeout."""

    @classmethod
    def from_settings(cls, settings: Any) -> TimeoutConfig:
        """Build the ceilings from configuration so they can be tuned per deployment."""
        config = cls(
            total_timeout_ms=int(settings.stage_timeout_total_ms),
            route_timeout_ms=int(settings.stage_timeout_route_ms),
            plan_timeout_ms=int(settings.stage_timeout_plan_ms),
            retrieval_timeout_ms=int(settings.stage_timeout_retrieval_ms),
            tool_timeout_ms=int(settings.stage_timeout_tool_ms),
            synthesis_timeout_ms=int(settings.stage_timeout_synthesis_ms),
            finalization_timeout_ms=int(settings.stage_timeout_finalization_ms),
            overhead_buffer_ms=int(settings.stage_timeout_overhead_ms),
        )
        config.validate()
        return config

    def stage_sum_ms(self) -> int:
        """One pass of every stage, plus overhead."""
        return (
            self.route_timeout_ms
            + self.plan_timeout_ms
            + self.retrieval_timeout_ms
            + self.tool_timeout_ms
            + self.synthesis_timeout_ms
            + self.finalization_timeout_ms
            + self.overhead_buffer_ms
        )

    def retry_round_ms(self) -> int:
        """What a verifier-directed retry costs: retrieval, synthesis, verification again.

        The graph's only loop re-enters at ``knowledge``, so a retry replays those
        three stages and nothing else.  The verifier consults this before asking
        for one: a retry the remaining budget cannot fund used to be started
        anyway and then killed by the total-budget check, turning a merely
        degraded answer into a failed request.
        """
        return self.retrieval_timeout_ms + self.synthesis_timeout_ms + self.finalization_timeout_ms

    def validate(self) -> None:
        """Validate that one pass of every stage fits inside the total timeout."""
        stage_sum = self.stage_sum_ms()

        if stage_sum > self.total_timeout_ms:
            raise ValueError(
                f"Stage timeouts sum ({stage_sum}ms) exceeds total timeout "
                f"({self.total_timeout_ms}ms). Reduce individual stage timeouts."
            )


class StageTimeoutError(Exception):
    """Raised when a stage exceeds its ceiling or the total budget is spent.

    Named for the stage rather than shadowing the builtin ``TimeoutError``, which
    is why this module previously had to reach for ``builtins.TimeoutError`` to
    catch asyncio's.
    """

    def __init__(self, stage: str, timeout_ms: int, elapsed_ms: int):
        self.stage = stage
        self.timeout_ms = timeout_ms
        self.elapsed_ms = elapsed_ms
        super().__init__(f"Stage '{stage}' exceeded timeout: {elapsed_ms}ms > {timeout_ms}ms")


# Stages that must run even when the total budget is spent. Both are security
# boundaries -- scope resolution on the way in, output DLP on the way out -- and
# both are deterministic, non-LLM and fast. Skipping either is not a degradation,
# it is a hole, so they are exempt from the total-budget gate and keep their own
# ceiling instead of being clamped to whatever is left.
MANDATORY_STAGES = frozenset({"privacy_permission", "output_filter"})


def deadline_offset_ms(deadline_at: datetime | None) -> int | None:
    """Convert a caller's absolute deadline into ms from now, measured once.

    Once, because everything after this is measured on ``perf_counter``: reading
    the wall clock per stage would let an NTP correction move a running request's
    budget. A naive datetime is read as UTC, matching the contracts that produce
    one (``datetime.now(UTC)``), rather than as local time -- guessing the
    caller's zone would silently shift the deadline by hours.
    """
    if deadline_at is None:
        return None
    moment = deadline_at if deadline_at.tzinfo is not None else deadline_at.replace(tzinfo=UTC)
    return int((moment - datetime.now(UTC)).total_seconds() * 1000)


class ExecutionBudget:
    """Tracks and enforces execution time budget across stages."""

    def __init__(self, config: TimeoutConfig, *, deadline_at: datetime | None = None):
        self.config = config
        self.start_time = time.perf_counter()
        self.stage_times: dict[str, float] = {}
        self.deadline_offset_ms = deadline_offset_ms(deadline_at)
        """A caller's own ceiling, or None. It only ever *narrows* the budget --
        see ``remaining_ms``."""

    def elapsed_ms(self) -> int:
        """Get total elapsed time in milliseconds."""
        return int((time.perf_counter() - self.start_time) * 1000)

    def remaining_ms(self) -> int:
        """Get remaining time budget in milliseconds.

        ``OrchestrationRequest.deadline_at`` is the caller saying "I stop caring
        at T". It is a ``min`` with the configured budget and never a
        replacement: a deadline further out than ``STAGE_TIMEOUT_TOTAL_MS`` must
        not let a caller pin a worker for an hour, and one already in the past
        must not extend anything either. Before 2026-08-31 the field had no
        reader at all, so a caller's deadline was accepted and ignored.
        """
        remaining = self.config.total_timeout_ms - self.elapsed_ms()
        if self.deadline_offset_ms is not None:
            remaining = min(remaining, self.deadline_offset_ms - self.elapsed_ms())
        return max(0, remaining)

    def has_budget(self, required_ms: int = 0) -> bool:
        """Check if sufficient budget remains."""
        return self.remaining_ms() >= required_ms

    def check_budget(self, stage: str) -> None:
        """Raise StageTimeoutError if the total budget is spent.

        Tests ``remaining_ms()`` directly rather than ``has_budget()``: with its
        default of ``required_ms=0`` that call reduced to ``remaining_ms() >= 0``,
        which ``remaining_ms``'s own ``max(0, ...)`` makes unconditionally true --
        so this gate had never once fired. An exhausted budget still surfaced,
        but as ``get_stage_timeout`` clamping the next stage to 0ms and asyncio
        cancelling it immediately, which reads in a trace as "the stage was slow"
        rather than "the request ran out of time".
        """
        if stage in MANDATORY_STAGES:
            return
        if self.remaining_ms() <= 0:
            raise StageTimeoutError(
                stage=stage,
                timeout_ms=self.config.total_timeout_ms,
                elapsed_ms=self.elapsed_ms(),
            )

    def record_stage(self, stage: str, duration_ms: int) -> None:
        """Record stage execution time."""
        self.stage_times[stage] = duration_ms

    def get_stage_timeout(self, stage: str) -> int:
        """Get timeout for specific stage, adjusted for remaining budget."""
        stage_timeouts = {
            "privacy_permission": self.config.finalization_timeout_ms,
            "route": self.config.route_timeout_ms,
            "plan": self.config.plan_timeout_ms,
            "knowledge_strategy": self.config.plan_timeout_ms,
            "rag": self.config.retrieval_timeout_ms,
            "knowledge": self.config.retrieval_timeout_ms,
            "tool": self.config.tool_timeout_ms,
            "synthesize": self.config.synthesis_timeout_ms,
            "verifier": self.config.finalization_timeout_ms,
            "finalize": self.config.finalization_timeout_ms,
            "output_filter": self.config.finalization_timeout_ms,
        }

        # Get configured timeout for stage
        stage_timeout = stage_timeouts.get(stage, 5000)

        # A mandatory stage keeps its own ceiling: clamping it to a spent budget
        # would give it 0ms and turn the security boundary into an instant failure.
        if stage in MANDATORY_STAGES:
            return stage_timeout

        # Never exceed remaining budget
        return min(stage_timeout, self.remaining_ms())

    def get_stats(self) -> dict[str, Any]:
        """Get execution statistics."""
        return {
            "total_elapsed_ms": self.elapsed_ms(),
            "total_budget_ms": self.config.total_timeout_ms,
            "caller_deadline_ms": self.deadline_offset_ms,
            "remaining_ms": self.remaining_ms(),
            "stage_times": dict(self.stage_times),
            "budget_utilization": self.elapsed_ms() / self.config.total_timeout_ms,
        }


@asynccontextmanager
async def stage_timeout(
    stage: str,
    budget: ExecutionBudget,
) -> AsyncIterator[None]:
    """Context manager for enforcing stage timeout.

    Usage:
        async with stage_timeout("route", budget):
            result = await router.route(request)
    """
    timeout_ms = budget.get_stage_timeout(stage)
    timeout_sec = timeout_ms / 1000.0
    start = time.perf_counter()

    try:
        async with asyncio.timeout(timeout_sec):
            yield
    except builtins.TimeoutError as exc:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        raise StageTimeoutError(stage, timeout_ms, elapsed_ms) from exc
    finally:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        budget.record_stage(stage, elapsed_ms)


async def run_with_timeout(
    stage: str,
    operation: Callable[[], Any],
    budget: ExecutionBudget,
) -> Any:
    """Run async operation with timeout enforcement.

    Raises:
        StageTimeoutError: If the operation exceeds its stage ceiling
        StageExecutionError: If operation fails for other reasons
    """
    # Check budget before starting
    budget.check_budget(stage)

    try:
        async with stage_timeout(stage, budget):
            return await operation()
    except StageTimeoutError:
        raise
    except Exception as exc:
        raise StageExecutionError(stage, exc) from exc


def get_timeout_config(profile: str) -> TimeoutConfig:
    """Get the timeout configuration for the given execution profile.

    Only one profile is currently supported; unrecognized values also fall back
    to it rather than raising.  Read from Settings on each call rather than
    frozen into a module constant, so a deployment can retune the ceilings
    without a code change -- the old hardcoded values (a 2s router covering up
    to three LLM calls, a 5s synthesis) fired on ordinary traffic.
    """
    del profile
    from app.core.config import get_settings

    return TimeoutConfig.from_settings(get_settings())
