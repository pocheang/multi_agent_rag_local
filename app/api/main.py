"""Stable FastAPI entry point and compatibility facade."""

# Historical imports below intentionally remain available from this module.
# ruff: noqa: F401

import logging
import sys

from app.api import dependencies as api_dependencies  # noqa: F401
from app.api.application import factory as _application_factory
from app.api.application import lifespan as _application_lifespan
from app.api.application import static_files as _application_static_files
from app.api.application.factory import (
    _APP_BASE_API_SEGMENTS,
    _LEGACY_API_PREFIX_SEGMENTS,
    _configure_cors,
    create_app,
    rewrite_app_prefixed_api_paths,
)
from app.api.application.lifespan import _auto_ingest_thread, lifespan
from app.api.application.router_registry import ROUTE_MODULES
from app.api.application.static_files import (
    build_frontend_handlers,
    resolve_static_file_paths,
)
from app.api.dependencies import (
    _auto_ingest_stop_event,
    auth_service,
    auto_ingest_watcher,
    settings,
)  # noqa: F401
from app.api.transport.errors import not_found  # noqa: F401
from app.api.transport.middleware import request_timing_middleware  # noqa: F401
from app.api.utils import (
    admin_helpers,
    auth_dependencies,
    auth_helpers,
    document_helpers,
    memory_helpers,
    session_helpers,
)  # noqa: F401 - these names remain part of the historical facade.

logger = logging.getLogger(__name__)

auth_dependencies.auth_service = auth_service
auth_helpers.auth_service = auth_service

# Preserve the historical module-level path and handler symbols.  The actual
# route handlers are owned by app.api.application.static_files and the same
# handler objects are registered on the public app below.
_STATIC_PATHS = resolve_static_file_paths()
react_dist_dir = _STATIC_PATHS.react_dist_dir
react_index_file = _STATIC_PATHS.react_index_file
react_assets_dir = _STATIC_PATHS.react_assets_dir
static_dir = _STATIC_PATHS.static_dir
_serve_react_index, serve_react_app_root, serve_react_app = build_frontend_handlers(_STATIC_PATHS)

# Keep this collection available for the historical monkeypatch bridge.  The
# tuple is canonicalized in app.api.application.router_registry.
_ROUTE_MODULES = ROUTE_MODULES
_APPLICATION_COMPAT_MODULES = (
    _application_factory,
    _application_lifespan,
    _application_static_files,
)

app = create_app(
    settings,
    static_paths=_STATIC_PATHS,
    static_handlers=(_serve_react_index, serve_react_app_root, serve_react_app),
)


def __getattr__(name: str):
    """Expose route/helper symbols for backward-compatible monkeypatching."""
    for module in _ROUTE_MODULES:
        if hasattr(module, name):
            return getattr(module, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")


class _CompatMainModule(type(sys)):
    """Propagate historical ``app.api.main`` monkeypatches to owners."""

    def __setattr__(self, name, value):
        super().__setattr__(name, value)
        for module in _ROUTE_MODULES:
            if hasattr(module, name):
                setattr(module, name, value)
        for module in _APPLICATION_COMPAT_MODULES:
            if hasattr(module, name):
                setattr(module, name, value)


sys.modules[__name__].__class__ = _CompatMainModule


__all__ = [
    "app",
    "lifespan",
    "create_app",
    "rewrite_app_prefixed_api_paths",
    "_configure_cors",
    "serve_react_app_root",
    "serve_react_app",
]
