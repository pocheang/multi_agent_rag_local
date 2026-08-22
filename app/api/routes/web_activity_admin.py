"""Compatibility alias for canonical admin web activity routes."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module("app.api.routes.admin.web_activity")
