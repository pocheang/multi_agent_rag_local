"""Lazy lifecycle adapters for legacy agent runtime hooks."""

from __future__ import annotations


def warm_nli_model() -> None:
    """Load the NLI model during application startup."""
    from app.agents.validation.nli import get_nli_model

    get_nli_model()


def start_context_tracker_cleanup() -> None:
    """Start the legacy context-tracker cleanup task."""
    from app.services.sessions.context_tracker import start_background_cleanup

    start_background_cleanup()


def stop_context_tracker_cleanup() -> None:
    """Stop the legacy context-tracker cleanup task."""
    from app.services.sessions.context_tracker import stop_background_cleanup

    stop_background_cleanup()
