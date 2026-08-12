"""Focused answer-validation cascade with a lazy public export."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.validation.cascade import ValidationCascade

__all__ = ["ValidationCascade"]


def __getattr__(name: str):
    """Load the validation cascade only when it is requested."""
    if name == "ValidationCascade":
        from app.agents.validation.cascade import ValidationCascade

        return ValidationCascade
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
