"""Backward-compatible module alias for prompt persistence."""

import sys as _sys

from app.services.prompts import store as _canonical

_sys.modules[__name__] = _canonical
