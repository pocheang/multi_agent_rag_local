"""Safe execution-trace events for orchestration and future SSE delivery."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal

from pydantic import Field

from app.domain.contracts import ImmutableContract

EventStage = Literal[
    "privacy_permission",
    "route",
    "clarification",
    "plan",
    "knowledge",
    "rag",
    "tool",
    "synthesize",
    "verifier",
    "finalize",
    "output_filter",
    "complete",
    "failed",
]
EventStatus = Literal["completed", "failed", "skipped"]


class EventMetadata(ImmutableContract):
    """One safe, scalar field that may be shown in an execution trace."""

    key: str = Field(min_length=1, max_length=64)
    value: str = Field(max_length=1_000)


class ExecutionEvent(ImmutableContract):
    """A versioned, UI-safe stage outcome with no raw request or credential data."""

    version: Literal["1"] = "1"
    stage: EventStage
    status: EventStatus
    duration_ms: int = Field(default=0, ge=0)
    message: str = Field(default="", max_length=1_000)
    metadata: tuple[EventMetadata, ...] = Field(default_factory=tuple, max_length=20)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
