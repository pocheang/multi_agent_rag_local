"""Typed application-scoped services for governed connector capabilities."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request

from app.agents.tool.factory import (
    ToolAgent,
    create_tool_agent,
    get_disable_connector_tool_id,
)
from app.api.dependencies import _require_permission, _require_user, settings
from app.domain.contracts import ToolResult
from app.mcp.approvals import ApprovalStore
from app.mcp.authorization import AuthorizationPolicy
from app.mcp.contracts import ToolCall, ToolDefinition
from app.mcp.gateway import MCPGateway
from app.mcp.registry import ToolRegistry
from app.orchestration.execution_events import ExecutionEventStore
from app.orchestration.request import RequestActor
from app.services.connectors.management import ConnectorManagementService, probe_http_connector
from app.services.connectors.metadata_repository import ConnectorMetadataRepository
from app.services.connectors.repository import CredentialRepository
from app.services.connectors.service import ConnectorCredentialService


@dataclass(frozen=True, slots=True)
class AppServices:
    """One dependency graph shared by browser routes and governed tools."""

    approvals: ApprovalStore
    tool_registry: ToolRegistry
    gateway: MCPGateway
    connectors: ConnectorManagementService
    execution_events: ExecutionEventStore
    tool_agent: ToolAgent


def build_app_services() -> AppServices:
    """Build governed tools and connector services around shared application state."""
    approvals = ApprovalStore()
    execution_events = ExecutionEventStore()
    registry = ToolRegistry(
        authorization=AuthorizationPolicy(), approvals=approvals, execution_events=execution_events
    )
    seed = str(settings.api_settings_encryption_key or "").strip()
    if not seed:
        raise RuntimeError("API_SETTINGS_ENCRYPTION_KEY is required for connector credentials")
    credentials = ConnectorCredentialService(
        CredentialRepository(),
        encryption_key=sha256(seed.encode("utf-8")).digest(),
    )
    connectors = ConnectorManagementService(
        ConnectorMetadataRepository(),
        credentials,
        probe=probe_http_connector,
    )
    gateway = MCPGateway(registry)

    async def disable_owned_connector(call: ToolCall, actor: RequestActor) -> ToolResult:
        connector_id = next(
            (argument.value for argument in call.arguments if argument.name == "connector_id"),
            "",
        )
        if not actor.user_id or not connector_id:
            return ToolResult(tool_id=call.tool_id, status="failed", summary="connector owner is required")
        try:
            connectors.disable(connector_id, actor.user_id)
        except KeyError:
            return ToolResult(tool_id=call.tool_id, status="failed", summary="owned connector not found")
        return ToolResult(tool_id=call.tool_id, status="succeeded", summary="connector disabled")

    registry.register(
        ToolDefinition(tool_id=get_disable_connector_tool_id(), operation="write"),
        disable_owned_connector,
    )
    tool_agent = create_tool_agent(gateway, connectors)
    return AppServices(
        approvals=approvals,
        tool_registry=registry,
        gateway=gateway,
        connectors=connectors,
        execution_events=execution_events,
        tool_agent=tool_agent,
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
    try:
        return get_app_services(request.app)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Application services unavailable") from exc


def get_approval_store(services: AppServices = Depends(require_app_services)) -> ApprovalStore:
    """Inject the same store used by the production tool registry."""
    return services.approvals


def get_connector_service(
    services: AppServices = Depends(require_app_services),
) -> ConnectorManagementService:
    """Inject owner-scoped connector management."""
    return services.connectors


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
    _require_permission(user, "query:run", request, "orchestration")
    return require_request_actor(user)

