"""Prompt persistence and report-editing capability public surface."""

from typing import Any

__all__ = [
    "AIEditOperation",
    "AIEditRequest",
    "AIEditResponse",
    "AIReportEditor",
    "PromptStore",
    "get_ai_report_editor",
]


def __getattr__(name: str) -> Any:
    """Lazily expose canonical owners without eager model initialization imports."""
    if name == "PromptStore":
        from .store import PromptStore

        return PromptStore
    if name in {
        "AIEditOperation",
        "AIEditRequest",
        "AIEditResponse",
        "AIReportEditor",
        "get_ai_report_editor",
    }:
        from . import report_editor

        return getattr(report_editor, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
