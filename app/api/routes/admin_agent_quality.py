"""Compatibility alias for the canonical admin agent-quality routes."""

import sys as _sys
from importlib import import_module as _import_module

_sys.modules[__name__] = _import_module("app.api.routes.admin.agent_quality")
