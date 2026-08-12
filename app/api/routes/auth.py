"""Compatibility alias for :mod:`app.api.routes.public.auth`."""

import sys as _sys

from app.api.routes.public import auth as _canonical

_sys.modules[__name__] = _canonical
