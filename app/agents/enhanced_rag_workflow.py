"""Compatibility module alias for :mod:`app.workflow.enhanced_rag_workflow`.

The module-object alias preserves established import and monkeypatch targets.
"""

from importlib import import_module as _import_module
import sys as _sys

_sys.modules[__name__] = _import_module("app.workflow.enhanced_rag_workflow")
