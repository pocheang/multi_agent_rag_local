"""Errors intentionally exposed by orchestration boundaries."""

from __future__ import annotations


class OrchestrationError(RuntimeError):
    """Base error for a failed orchestration request."""


class StageExecutionError(OrchestrationError):
    """A named stage failed before a final answer could be created."""

    def __init__(self, stage: str, cause: Exception) -> None:
        super().__init__(f"orchestration stage '{stage}' failed: {cause}")
        self.stage = stage
        self.__cause__ = cause
