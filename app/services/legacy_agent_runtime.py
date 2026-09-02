"""Lazy lifecycle adapters for legacy agent runtime hooks."""

from __future__ import annotations


def warm_nli_model() -> None:
    """Load the NLI model during application startup."""
    from app.agents.validation.nli import get_nli_model

    get_nli_model()
