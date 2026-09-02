"""Typed application-scoped services for governed connector capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request

from app.agents.tool.factory import ToolAgent, create_tool_agent
from app.api.dependencies import _require_permission, _require_user
from app.mcp.approvals import ApprovalStore
from app.mcp.gateway import MCPGateway
from app.mcp.registry import ToolRegistry
from app.mcp.runtime import get_tool_stack
from app.orchestration.answer_stream import AnswerStreamStore, get_default_answer_stream_store
from app.orchestration.execution_events import ExecutionEventStore, get_default_execution_event_store
from app.orchestration.request import RequestActor
from app.services.connectors.management import ConnectorManagementService
from app.services.security.rbac import Permission


@dataclass(frozen=True, slots=True)
class AppServices:
    """One dependency graph shared by browser routes and governed tools."""

    approvals: ApprovalStore
    tool_registry: ToolRegistry
    gateway: MCPGateway
    connectors: ConnectorManagementService
    execution_events: ExecutionEventStore
    answer_stream: AnswerStreamStore
    tool_agent: ToolAgent


def build_app_services() -> AppServices:
    """Expose the process-wide governed tool stack through the FastAPI container.

    Everything here is *resolved*, not constructed. The stack this hands out is
    the same one the RAG pipeline reaches through
    ``app.mcp.runtime.get_tool_stack``: an approval token minted by a tool call
    inside the pipeline has to be redeemable at
    ``POST /api/v1/connectors/approvals/{token}``, which only holds if both
    sides share one ``ApprovalStore``.
    """
    stack = get_tool_stack()
    return AppServices(
        approvals=stack.approvals,
        tool_registry=stack.registry,
        gateway=stack.gateway,
        connectors=stack.connectors,
        # The same process-wide store RAGPipeline publishes into; a private
        # instance here would leave the SSE endpoint blind to pipeline events.
        execution_events=get_default_execution_event_store(),
        answer_stream=get_default_answer_stream_store(),
        tool_agent=create_tool_agent(stack.gateway, stack.registry),
    )


def install_app_services(app: FastAPI) -> AppServices:
    """Install one typed service container for the lifetime of an application."""
    services = build_app_services()
    app.state.querymind_services = services
    return services


def get_app_services(app: FastAPI) -> AppServices:
    """Read the installed container for trusted in-process integrations."""
    services = getattr(app.state, "querymind_services", None)
    if services is None:
        # Lifespan installs the container in production.  Initializing here
        # keeps embedded ASGI hosts on the same typed capability graph instead
        # of falling back to an ungoverned tool path.
        services = install_app_services(app)
    if not isinstance(services, AppServices):
        raise RuntimeError("application services are not installed")
    return services


def require_app_services(request: Request) -> AppServices:
    """Fail closed when a router is mounted outside the production application."""
    services = getattr(request.app.state, "querymind_services", None)
    if not isinstance(services, AppServices):
        raise HTTPException(status_code=503, detail="Application services unavailable")
    return services


def get_approval_store(services: AppServices = Depends(require_app_services)) -> ApprovalStore:
    """Inject the same store used by the production tool registry."""
    return services.approvals


def get_connector_service(
    services: AppServices = Depends(require_app_services),
) -> ConnectorManagementService:
    """Inject owner-scoped connector management."""
    return services.connectors


def get_answer_stream_store(
    services: AppServices = Depends(require_app_services),
) -> AnswerStreamStore:
    """Inject the app-scoped redacted answer-draft stream."""
    return services.answer_stream


def get_execution_event_store(
    services: AppServices = Depends(require_app_services),
) -> ExecutionEventStore:
    """Inject the app-scoped stream store shared with governed tools."""
    return services.execution_events


def require_request_actor(user: dict[str, Any] = Depends(_require_user)) -> RequestActor:
    """Adapt legacy authentication output once into an immutable actor contract."""
    return RequestActor(
        user_id=str(user.get("user_id") or "") or None,
        username=str(user.get("username") or "") or None,
        role=str(user.get("role") or "") or None,
        permissions=frozenset(str(item) for item in (user.get("permissions") or ())),
    )


def require_trace_actor(request: Request, user: dict[str, Any] = Depends(_require_user)) -> RequestActor:
    """Authorize trace access at the HTTP edge, then expose only a bounded actor."""
    _require_permission(user, Permission.QUERY_RUN, request, "orchestration")
    return require_request_actor(user)
