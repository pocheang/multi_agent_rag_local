"""Backward-compatible module alias for AI report editing."""

import sys as _sys

from app.services.prompts import report_editor as _canonical

_sys.modules[__name__] = _canonical
