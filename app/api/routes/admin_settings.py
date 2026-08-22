"""Compatibility alias for canonical admin settings routes."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module("app.api.routes.admin.settings")
