"""Compatibility module for canonical graph entity extraction."""

from importlib import import_module as _import_module
import sys as _sys

_sys.modules[__name__] = _import_module("app.graph.knowledge.entity_extraction")
