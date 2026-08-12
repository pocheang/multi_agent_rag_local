"""Compatibility alias for the canonical public prompts routes."""

from importlib import import_module
import sys

sys.modules[__name__] = import_module("app.api.routes.public.prompts")
