"""Compatibility alias for :mod:`app.api.routes.public.query`."""

import sys as _sys

from app.api.routes.public import query as _canonical

_sys.modules[__name__] = _canonical
