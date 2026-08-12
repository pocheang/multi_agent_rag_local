"""Compatibility alias for canonical admin settings routes."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module("app.api.routes.admin.settings")
