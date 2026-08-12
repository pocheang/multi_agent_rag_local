"""Compatibility alias for the canonical service owner."""

from importlib import import_module as _import_module
import sys as _sys

_sys.modules[__name__] = _import_module("app.services.runtime.rag_runtime_scope")

