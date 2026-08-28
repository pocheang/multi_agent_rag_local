"""
Unified error handling and degradation strategies for orchestration.

Design Principles:
1. Explicit degradation policies - never silently fail
2. Configurable failure thresholds
3. Clear error propagation with context
4. Structured error reporting for observability
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class FailureMode(StrEnum):
    """How to handle component failures."""

    STRICT = "strict"  # Fail immediately on any error
    GRACEFUL = "graceful"  # Continue with degraded results if possible
    BEST_EFFORT = "best_effort"  # Continue even with all failures


class ComponentType(StrEnum):
    """Orchestration component types."""

    ROUTER = "router"
    PLANNER = "planner"
    RETRIEVER = "retriever"
    TOOL_RUNNER = "tool"
    SYNTHESIZER = "synthesizer"
    FINALIZER = "finalizer"


@dataclass
class DegradationPolicy:
    """Policy for handling component failures and degradation.

    Defines minimum quality requirements and fallback strategies.
    """

    # Retrieval degradation
    min_retrievers_required: int = 1
    """Minimum number of successful retrievers (vector, bm25, graph, web).
    WHY: At least one retriever must succeed to provide evidence."""

    min_evidence_items: int = 1
    """Minimum evidence items required for synthesis.
    WHY: Cannot generate citation-backed answer without evidence."""

    allow_partial_retrieval: bool = True
    """Allow synthesis with some failed retrievers.
    WHY: Vector + BM25 may succeed while graph/web fails."""

    # Validation degradation
    require_validation: bool = True
    """Require answer validation to complete.
    WHY: Quality assurance is critical for production."""

    allow_degraded_validation: bool = True
    """Allow answers with validation warnings (not failures).
    WHY: Some validation checks may time out but answer is still usable."""

    # Failure modes per component
    router_failure_mode: FailureMode = FailureMode.STRICT
    """Router must succeed - no fallback route is safe."""

    planner_failure_mode: FailureMode = FailureMode.GRACEFUL
    """Planner can fail - use single-task fallback."""

    retriever_failure_mode: FailureMode = FailureMode.GRACEFUL
    """Retriever can partially fail - see min_retrievers_required."""

    tool_failure_mode: FailureMode = FailureMode.GRACEFUL
    """Tool execution can fail - synthesis proceeds without tool results."""

    synthesizer_failure_mode: FailureMode = FailureMode.STRICT
    """Synthesizer must succeed - answer generation is core."""

    finalizer_failure_mode: FailureMode = FailureMode.GRACEFUL
    """Finalizer can degrade - return answer with degraded validation."""

    def validate_retrieval(
        self,
        total_retrievers: int,
        successful_retrievers: int,
        evidence_count: int,
    ) -> tuple[bool, str | None]:
        """Validate retrieval results against policy.

        Returns:
            (is_valid, error_message)
        """
        if successful_retrievers == 0:
            return False, f"All {total_retrievers} retrievers failed"

        if successful_retrievers < self.min_retrievers_required:
            return False, (
                f"Only {successful_retrievers}/{total_retrievers} retrievers succeeded, "
                f"minimum required: {self.min_retrievers_required}"
            )

        if evidence_count < self.min_evidence_items:
            return False, (
                f"Only {evidence_count} evidence items retrieved, minimum required: {self.min_evidence_items}"
            )

        return True, None

    def should_retry_on_failure(self, component: ComponentType) -> bool:
        """Determine if component failure should trigger retry."""
        mode_map = {
            ComponentType.ROUTER: self.router_failure_mode,
            ComponentType.PLANNER: self.planner_failure_mode,
            ComponentType.RETRIEVER: self.retriever_failure_mode,
            ComponentType.TOOL_RUNNER: self.tool_failure_mode,
            ComponentType.SYNTHESIZER: self.synthesizer_failure_mode,
            ComponentType.FINALIZER: self.finalizer_failure_mode,
        }
        mode = mode_map.get(component, FailureMode.STRICT)
        # Only STRICT mode failures trigger retries
        return mode == FailureMode.STRICT


@dataclass
class ErrorContext:
    """Rich error context for debugging and observability."""

    component: ComponentType
    stage: str
    error_type: str
    error_message: str
    metadata: dict[str, Any]
    is_retryable: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for logging/reporting."""
        return {
            "component": self.component.value,
            "stage": self.stage,
            "error_type": self.error_type,
            "error_message": self.error_message,
            "metadata": self.metadata,
            "is_retryable": self.is_retryable,
        }


class RetrievalDegradationError(RuntimeError):
    """Raised when retrieval fails degradation policy checks."""

    def __init__(
        self,
        message: str,
        total_retrievers: int,
        successful_retrievers: int,
        evidence_count: int,
        failed_retrievers: list[str],
    ):
        super().__init__(message)
        self.total_retrievers = total_retrievers
        self.successful_retrievers = successful_retrievers
        self.evidence_count = evidence_count
        self.failed_retrievers = failed_retrievers


class ValidationDegradationError(RuntimeError):
    """Raised when validation fails but answer may still be usable."""

    def __init__(self, message: str, validation_issues: tuple[str, ...]):
        super().__init__(message)
        self.validation_issues = validation_issues

