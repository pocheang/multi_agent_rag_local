"""Compatibility module for the canonical model runtime service."""

from importlib import import_module as _import_module
import sys as _sys

_sys.modules[__name__] = _import_module("app.services.models.runtime")
