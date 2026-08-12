"""Compatibility alias for :mod:`app.services.query.guard`."""

from importlib import import_module as _import_module
import sys as _sys

_sys.modules[__name__] = _import_module("app.services.query.guard")
