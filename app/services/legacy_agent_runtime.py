"""Lazy lifecycle adapters for legacy agent runtime hooks."""

from __future__ import annotations


def warm_nli_model() -> None:
    """Load the NLI model during application startup.

    Two things were wrong with this before. It reached `get_nli_model()`, which
    warmed a module-level `NLIValidator` instance that was *not* the one
    `ValidationCascade` constructs -- so the thing warmed was never the thing
    that ran. And the loader had no `local_files_only=True`, so on a machine
    without the model this started an untimed HuggingFace download on the event
    loop during startup.

    The shared `lru_cache`d loader fixes both: one model per process, and a
    missing model returns None immediately.
    """

    from app.agents.validation.nli import load_nli_cross_encoder

    load_nli_cross_encoder()
