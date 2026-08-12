"""One-time approval token lifecycle for high-risk MCP calls."""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from app.mcp.contracts import ApprovalRequest, ToolCall
from app.orchestration.request import RequestActor


class ApprovalStore:
    """In-memory approval store; persistence can replace this service without changing Registry."""

    def __init__(self) -> None:
        self._requests: dict[str, ApprovalRequest] = {}

    def create(self, call: ToolCall, actor: RequestActor) -> ApprovalRequest:
        """Create an approval token bound to one actor and tool."""
        actor_id = _actor_id(actor)
        request = ApprovalRequest(
            tool_id=call.tool_id,
            actor_id=actor_id,
            call_fingerprint=_call_fingerprint(call),
        )
        self._requests[request.token] = request
        return request

    def approve(self, token: str, actor: RequestActor) -> None:
        """Approve a valid, unexpired token for its original actor only."""
        request = self._request_for_actor(token, actor)
        if request.consumed or request.expires_at <= datetime.now(UTC):
            raise ValueError("approval token is no longer valid")
        self._requests[token] = request.model_copy(update={"approved": True, "approved_by": _actor_id(actor)})

    def consume(self, call: ToolCall, actor: RequestActor) -> ApprovalRequest | None:
        """Atomically consume and return an approved token for one matching call."""
        if not call.approval_token:
            return None
        try:
            request = self._request_for_actor(call.approval_token, actor)
        except ValueError:
            return None
        if (
            request.tool_id != call.tool_id
            or request.call_fingerprint != _call_fingerprint(call)
            or not request.approved
            or request.consumed
            or request.expires_at <= datetime.now(UTC)
        ):
            return None
        consumed = request.model_copy(update={"consumed": True})
        self._requests[request.token] = consumed
        return consumed

    def _request_for_actor(self, token: str, actor: RequestActor) -> ApprovalRequest:
        request = self._requests.get(token)
        if request is None or request.actor_id != _actor_id(actor):
            raise ValueError("approval token is not available to this actor")
        return request


def _call_fingerprint(call: ToolCall) -> str:
    digest = sha256()
    values = ((call.tool_id, call.execution_id), *((argument.name, argument.value) for argument in call.arguments))
    for pair in values:
        for value in pair:
            encoded = value.encode("utf-8")
            digest.update(len(encoded).to_bytes(4, "big"))
            digest.update(encoded)
    return digest.hexdigest()


def _actor_id(actor: RequestActor) -> str:
    if not actor.user_id:
        raise ValueError("approval requires an authenticated actor")
    return actor.user_id
