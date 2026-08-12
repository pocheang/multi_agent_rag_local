"""Compatibility alias for the canonical admin route owner."""

import sys as _sys
from importlib import import_module as _import_module

_sys.modules[__name__] = _import_module("app.api.routes.admin.language_stats")
