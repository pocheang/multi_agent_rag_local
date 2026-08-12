"""Compatibility module for the canonical HTTP schema package."""

from importlib import import_module as _import_module
import sys as _sys

_sys.modules[__name__] = _import_module("app.api.schemas.http")
