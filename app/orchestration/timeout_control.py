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
from typing import Any

from app.domain.errors import StageExecutionError


@dataclass
class TimeoutConfig:
    """Timeout configuration for orchestration stages.

    All timeouts in milliseconds for consistency.
    """

    # Overall orchestration timeout
    total_timeout_ms: int = 30000  # 30 seconds default
    """Maximum time for entire orchestration execution.
    WHY: Prevent requests from hanging indefinitely."""

    # Per-stage timeouts
    route_timeout_ms: int = 2000  # 2 seconds
    """Router decision timeout.
    WHY: Route selection should be fast, LLM-based routing is expensive."""

    plan_timeout_ms: int = 3000  # 3 seconds
    """Query decomposition timeout.
    WHY: Planning is optional, should not dominate latency."""

    retrieval_timeout_ms: int = 10000  # 10 seconds
    """Retrieval stage timeout (all retrievers combined).
    WHY: Most expensive stage, but must complete for synthesis."""

    tool_timeout_ms: int = 15000  # 15 seconds
    """Tool execution timeout.
    WHY: External tool calls may be slow (web search, API calls)."""

    synthesis_timeout_ms: int = 10000  # 10 seconds
    """Answer synthesis timeout.
    WHY: LLM generation can be slow for long answers."""

    finalization_timeout_ms: int = 5000  # 5 seconds
    """Validation and finalization timeout.
    WHY: Quality checks should not double total latency."""

    # Buffer for overhead
    overhead_buffer_ms: int = 1000  # 1 second
    """Buffer for orchestration overhead (event publishing, type conversions).
    WHY: Sum of stage timeouts should not exceed total timeout."""

    def validate(self) -> None:
        """Validate that stage timeouts sum to less than total timeout."""
        stage_sum = (
            self.route_timeout_ms
            + self.plan_timeout_ms
            + self.retrieval_timeout_ms
            + self.tool_timeout_ms
            + self.synthesis_timeout_ms
            + self.finalization_timeout_ms
            + self.overhead_buffer_ms
        )

        if stage_sum > self.total_timeout_ms:
            raise ValueError(
                f"Stage timeouts sum ({stage_sum}ms) exceeds total timeout "
                f"({self.total_timeout_ms}ms). Reduce individual stage timeouts."
            )


class TimeoutError(Exception):
    """Raised when operation exceeds timeout budget."""

    def __init__(self, stage: str, timeout_ms: int, elapsed_ms: int):
        self.stage = stage
        self.timeout_ms = timeout_ms
        self.elapsed_ms = elapsed_ms
        super().__init__(f"Stage '{stage}' exceeded timeout: {elapsed_ms}ms > {timeout_ms}ms")


class ExecutionBudget:
    """Tracks and enforces execution time budget across stages."""

    def __init__(self, config: TimeoutConfig):
        self.config = config
        self.start_time = time.perf_counter()
        self.stage_times: dict[str, float] = {}

    def elapsed_ms(self) -> int:
        """Get total elapsed time in milliseconds."""
        return int((time.perf_counter() - self.start_time) * 1000)

    def remaining_ms(self) -> int:
        """Get remaining time budget in milliseconds."""
        return max(0, self.config.total_timeout_ms - self.elapsed_ms())

    def has_budget(self, required_ms: int = 0) -> bool:
        """Check if sufficient budget remains."""
        return self.remaining_ms() >= required_ms

    def check_budget(self, stage: str) -> None:
        """Raise TimeoutError if total budget exceeded."""
        if not self.has_budget():
            raise TimeoutError(
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
            "clarification": self.config.route_timeout_ms,
            "plan": self.config.plan_timeout_ms,
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

        # Never exceed remaining budget
        return min(stage_timeout, self.remaining_ms())

    def get_stats(self) -> dict[str, Any]:
        """Get execution statistics."""
        return {
            "total_elapsed_ms": self.elapsed_ms(),
            "total_budget_ms": self.config.total_timeout_ms,
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
        raise TimeoutError(stage, timeout_ms, elapsed_ms) from exc
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
        TimeoutError: If operation exceeds stage timeout
        StageExecutionError: If operation fails for other reasons
    """
    # Check budget before starting
    budget.check_budget(stage)

    try:
        async with stage_timeout(stage, budget):
            return await operation()
    except TimeoutError:
        raise
    except Exception as exc:
        raise StageExecutionError(stage, exc) from exc


# Profile-specific timeout configurations

STANDARD_TIMEOUT = TimeoutConfig(
    total_timeout_ms=30000,
    route_timeout_ms=2000,
    plan_timeout_ms=2000,
    retrieval_timeout_ms=10000,
    tool_timeout_ms=8000,
    synthesis_timeout_ms=5000,
    finalization_timeout_ms=2000,
    overhead_buffer_ms=1000,
)

STRICT_QUALITY_TIMEOUT = TimeoutConfig(
    total_timeout_ms=60000,  # Allow more time for quality checks
    route_timeout_ms=3000,
    plan_timeout_ms=3000,
    retrieval_timeout_ms=20000,  # More time for thorough retrieval
    tool_timeout_ms=15000,
    synthesis_timeout_ms=10000,
    finalization_timeout_ms=7000,  # More time for validation
    overhead_buffer_ms=2000,
)

FAST_TIMEOUT = TimeoutConfig(
    total_timeout_ms=15000,  # Fast responses
    route_timeout_ms=1000,
    plan_timeout_ms=1000,
    retrieval_timeout_ms=5000,
    tool_timeout_ms=3000,
    synthesis_timeout_ms=3000,
    finalization_timeout_ms=1000,
    overhead_buffer_ms=1000,
)

# Validate all configurations at module load time
STANDARD_TIMEOUT.validate()
STRICT_QUALITY_TIMEOUT.validate()
FAST_TIMEOUT.validate()


def get_timeout_config(profile: str) -> TimeoutConfig:
    """Get timeout configuration for execution profile.

    All configurations are pre-validated at module load time,
    so this function never raises validation errors.
    """
    configs = {
        "standard": STANDARD_TIMEOUT,
        "strict_quality": STRICT_QUALITY_TIMEOUT,
        "advanced": STANDARD_TIMEOUT,
        "fast": FAST_TIMEOUT,
    }
    return configs.get(profile, STANDARD_TIMEOUT)
