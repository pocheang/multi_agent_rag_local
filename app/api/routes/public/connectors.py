"""Browser-facing connector APIs with no tool execution."""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Path, status
from pydantic import Field

from app.api.deps.runtime import get_approval_store, get_connector_service, require_request_actor
from app.api.transport.errors import bad_request, conflict, not_found
from app.domain.contracts import ImmutableContract
from app.mcp.approvals import ApprovalStore
from app.orchestration.request import RequestActor
from app.services.connectors.contracts import ConnectorHost, ConnectorProbeResult, ConnectorURL, ConnectorView
from app.services.connectors.management import ConnectorManagementService

router = APIRouter(prefix="/api/v1/connectors", tags=["connectors"])

ConnectorIdPath = Annotated[
    str,
    Path(min_length=1, max_length=64, pattern=r"^[a-z][a-z0-9_-]{0,63}$"),
]


class ApprovalConfirmationRequest(ImmutableContract):
    """Explicit browser confirmation for an existing one-time approval token."""

    confirmed: bool


class ApprovalConfirmationResponse(ImmutableContract):
    """Safe result returned after a token has been approved."""

    approval_status: Literal["approved"] = "approved"


class ConnectorCreateRequest(ImmutableContract):
    """Bounded connector configuration accepted from the browser."""

    connector_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    name: str = Field(min_length=1, max_length=120)
    base_url: ConnectorURL
    allowed_hosts: frozenset[ConnectorHost] = Field(min_length=1, max_length=20)
    secret: str = Field(min_length=1, max_length=8_000)


class ConnectorListResponse(ImmutableContract):
    """Owner-scoped connector metadata list."""

    connectors: tuple[ConnectorView, ...] = Field(default_factory=tuple, max_length=100)


@router.get("", response_model=ConnectorListResponse)
async def list_connectors(
    actor: RequestActor = Depends(require_request_actor),
    service: ConnectorManagementService = Depends(get_connector_service),
) -> ConnectorListResponse:
    """Return only connector metadata owned by the authenticated actor."""
    return ConnectorListResponse(connectors=service.list_for_owner(_owner_id(actor)))


@router.post("", response_model=ConnectorView, status_code=status.HTTP_201_CREATED)
async def create_connector(
    body: ConnectorCreateRequest,
    actor: RequestActor = Depends(require_request_actor),
    service: ConnectorManagementService = Depends(get_connector_service),
) -> ConnectorView:
    """Store encrypted credentials and return only a server-managed redaction."""
    try:
        return service.create(
            connector_id=body.connector_id,
            owner_id=_owner_id(actor),
            name=body.name,
            base_url=str(body.base_url),
            allowed_hosts=body.allowed_hosts,
            secret=body.secret,
        )
    except ValueError as exc:
        if "already exists" in str(exc):
            raise conflict("connector already exists") from exc
        raise bad_request(str(exc)) from exc


@router.post("/{connector_id}/disable", response_model=ConnectorView)
async def disable_connector(
    connector_id: ConnectorIdPath,
    actor: RequestActor = Depends(require_request_actor),
    service: ConnectorManagementService = Depends(get_connector_service),
) -> ConnectorView:
    """Disable one owner-scoped connector without deleting its audit identity."""
    try:
        return service.disable(connector_id, _owner_id(actor))
    except KeyError as exc:
        raise not_found("Connector") from exc


@router.post("/{connector_id}/enable", response_model=ConnectorView)
async def enable_connector(
    connector_id: ConnectorIdPath,
    actor: RequestActor = Depends(require_request_actor),
    service: ConnectorManagementService = Depends(get_connector_service),
) -> ConnectorView:
    """Re-enable one owner-scoped connector while retaining its audit identity."""
    try:
        return service.enable(connector_id, _owner_id(actor))
    except KeyError as exc:
        raise not_found("Connector") from exc


@router.post("/{connector_id}/test", response_model=ConnectorProbeResult)
async def test_connector(
    connector_id: ConnectorIdPath,
    actor: RequestActor = Depends(require_request_actor),
    service: ConnectorManagementService = Depends(get_connector_service),
) -> ConnectorProbeResult:
    """Run the service's bounded read-only reachability probe."""
    try:
        return await service.test(connector_id, _owner_id(actor))
    except KeyError as exc:
        raise not_found("Connector") from exc
    except ValueError as exc:
        raise conflict(str(exc)) from exc


@router.post("/approvals/{token}", response_model=ApprovalConfirmationResponse)
async def confirm_approval(
    token: Annotated[str, Path(max_length=256)],
    body: ApprovalConfirmationRequest,
    actor: RequestActor = Depends(require_request_actor),
    approval_store: ApprovalStore = Depends(get_approval_store),
) -> ApprovalConfirmationResponse:
    """Approve one actor-bound token; tool execution stays outside this boundary."""
    if not body.confirmed:
        raise bad_request("approval confirmation is required")
    try:
        approval_store.approve(token, actor)
    except ValueError as exc:
        raise not_found("Approval") from exc
    return ApprovalConfirmationResponse()


def _owner_id(actor: RequestActor) -> str:
    if not actor.user_id:
        raise bad_request("authenticated connector owner is required")
    return actor.user_id
