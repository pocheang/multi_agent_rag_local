"""Typed router adapter with a lazy public service export."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.agents.router.service import RouterAgentService

__all__ = ["RouterAgentService"]


def __getattr__(name: str):
    """Load the optional router service only when it is requested."""
    if name == "RouterAgentService":
        from app.agents.router.service import RouterAgentService

        return RouterAgentService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
