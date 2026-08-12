"""Compatibility alias for canonical admin web activity routes."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module("app.api.routes.admin.web_activity")
