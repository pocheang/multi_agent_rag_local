"""Compatibility alias for :mod:`app.api.routes.public.query_stream`."""

import sys as _sys

from app.api.routes.public import query_stream as _canonical

_sys.modules[__name__] = _canonical
