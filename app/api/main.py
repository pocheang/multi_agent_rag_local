"""Stable FastAPI entry point."""

import logging

from app.api.application.factory import create_app
from app.api.application.static_files import build_frontend_handlers, resolve_static_file_paths
from app.api.dependencies import settings

logger = logging.getLogger(__name__)

_STATIC_PATHS = resolve_static_file_paths()
_serve_react_index, serve_react_app_root, serve_react_app = build_frontend_handlers(_STATIC_PATHS)

app = create_app(
    settings,
    static_paths=_STATIC_PATHS,
    static_handlers=(_serve_react_index, serve_react_app_root, serve_react_app),
)

__all__ = ["app", "create_app", "serve_react_app", "serve_react_app_root"]
