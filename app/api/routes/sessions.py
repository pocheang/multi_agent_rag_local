"""Compatibility alias for the canonical public sessions routes."""

import sys
from importlib import import_module

sys.modules[__name__] = import_module("app.api.routes.public.sessions")
