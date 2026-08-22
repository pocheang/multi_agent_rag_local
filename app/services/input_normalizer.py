"""Compatibility alias for :mod:`app.services.query.input_normalizer`."""

import sys as _sys
from importlib import import_module as _import_module

_sys.modules[__name__] = _import_module("app.services.query.input_normalizer")
