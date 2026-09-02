"""Compatibility entry point for :mod:`app.services.documents.agent_scope`."""

import sys
from types import ModuleType

from app.services.documents import agent_scope as _agent_scope
from app.services.documents.agent_scope import (
    get_agent_filter_stats,
    get_sources_by_agent_class,
    read_corpus_records,
)


class _CompatibilityModule(ModuleType):
    """Keep legacy monkeypatches of the corpus reader effective for callers."""

    def __setattr__(self, name: str, value: object) -> None:
        super().__setattr__(name, value)
        if name == "read_corpus_records":
            setattr(_agent_scope, name, value)


sys.modules[__name__].__class__ = _CompatibilityModule

__all__ = [
    "get_agent_filter_stats",
    "get_sources_by_agent_class",
    "read_corpus_records",
]
