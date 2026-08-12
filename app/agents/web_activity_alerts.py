"""Compatibility alias for :mod:`app.services.web_activity.alerts`."""

from __future__ import annotations

import sys as _sys

from app.services.web_activity import alerts as _canonical_module

_sys.modules[__name__] = _canonical_module
