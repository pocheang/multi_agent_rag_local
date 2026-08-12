"""Canonical route registration metadata for the FastAPI application.

This module deliberately owns only application-composition metadata. Route
handlers remain in the grouped public/admin/operations/compatibility packages;
legacy flat paths are compatibility aliases.
"""

from fastapi import FastAPI

from app.api import dependencies as api_dependencies
from app.api.routes.admin import agent_quality as admin_agent_quality
from app.api.routes.admin import graph_rag as admin_graph_rag
from app.api.routes.admin import language_stats as admin_language_stats
from app.api.routes.admin import ops as admin_ops
from app.api.routes.admin import settings as admin_settings
from app.api.routes.admin import users as admin_users
from app.api.routes.admin import web_activity as web_activity_admin
from app.api.routes.compatibility import advanced_rag, enhanced_query, orchestration, pipeline_compat
from app.api.routes.operations import agent_health, agent_tracking, analytics, evaluation, health
from app.api.routes.public import auth, connectors, documents, prompts, query, sessions
from app.api.utils import (
    admin_helpers,
    auth_dependencies,
    auth_helpers,
    document_helpers,
    memory_helpers,
    query_helpers,
    session_helpers,
)

# Keep this collection in the exact order used by app.api.main's compatibility
# monkeypatch bridge.  pipeline_compat is intentionally included even though it
# is not itself registered as a router.
_ROUTE_MODULES = (
    api_dependencies,
    admin_helpers,
    auth_dependencies,
    auth_helpers,
    document_helpers,
    health,
    memory_helpers,
    query_helpers,
    session_helpers,
    auth,
    query,
    sessions,
    documents,
    prompts,
    admin_users,
    admin_ops,
    pipeline_compat,
    admin_settings,
    admin_language_stats,
    agent_tracking,
    evaluation,
    advanced_rag,
    analytics,
    enhanced_query,
)

# Public spelling for application-composition callers; it is the same tuple so
# consumers cannot observe a divergent compatibility module collection.
ROUTE_MODULES = _ROUTE_MODULES

# Preserve the include_router order from app.api.main exactly.  These modules
# are the sole source of router objects; this registry adds no route behavior.
ROUTER_MODULES = (
    health,
    auth,
    connectors,
    query,
    sessions,
    documents,
    prompts,
    admin_users,
    admin_ops,
    admin_settings,
    admin_language_stats,
    admin_agent_quality,
    agent_tracking,
    agent_health,
    evaluation,
    advanced_rag,
    analytics,
    admin_graph_rag,
    enhanced_query,
    orchestration,
    web_activity_admin,
)


def register_routers(app: FastAPI) -> None:
    """Register the application's existing routers in their frozen order."""
    for route_module in ROUTER_MODULES:
        app.include_router(route_module.router)


__all__ = [
    "ROUTE_MODULES",
    "ROUTER_MODULES",
    "_ROUTE_MODULES",
    "register_routers",
]
