"""Canonical route registration metadata for the FastAPI application.

This module owns only application composition. Route handlers live in the
grouped public/admin/operations/compatibility packages.
"""

from fastapi import FastAPI

from app.api.routes import sessions as sessions_management
from app.api.routes.admin import agent_quality as admin_agent_quality
from app.api.routes.admin import graph_rag as admin_graph_rag
from app.api.routes.admin import language_stats as admin_language_stats
from app.api.routes.admin import ops as admin_ops
from app.api.routes.admin import settings as admin_settings
from app.api.routes.admin import users as admin_users
from app.api.routes.admin import web_activity as web_activity_admin
from app.api.routes.operations import agent_health, agent_tracking, analytics, evaluation, health
from app.api.routes.optimization import performance as optimization_performance
from app.api.routes.public import auth, clarification, connectors, documents, orchestration, prompts
from app.api.routes.public import query as advanced_rag
from app.api.routes.public import sessions as public_sessions

# These modules are the sole source of router objects; this registry adds no
# route behavior.
ROUTER_MODULES = (
    health,
    auth,
    clarification,
    connectors,
    public_sessions,
    sessions_management,
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
    orchestration,
    web_activity_admin,
    optimization_performance,
)


def register_routers(app: FastAPI) -> None:
    """Register the application's existing routers in their frozen order."""
    for route_module in ROUTER_MODULES:
        app.include_router(route_module.router)


__all__ = ["ROUTER_MODULES", "register_routers"]
