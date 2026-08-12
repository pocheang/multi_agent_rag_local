"""Read-only REST connector with URL allowlist enforcement."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from urllib.parse import urljoin, urlparse

from app.domain.contracts import ToolResult
from app.mcp.contracts import ConnectorDefinition, RestRequest, RestResponse, ToolArgument, ToolCall
from app.orchestration.request import RequestActor

RestTransport = Callable[[RestRequest], Awaitable[RestResponse]]


class RestConnector:
    """Execute read-only relative REST paths against one allowlisted base URL."""

    def __init__(self, definition: ConnectorDefinition, *, transport: RestTransport) -> None:
        self._definition = definition
        self._transport = transport

    async def invoke(self, call: ToolCall, actor: RequestActor) -> ToolResult:
        """Reject unsafe paths before an outbound request can be attempted."""
        del actor
        path = _argument_value(call.arguments, "path")
        if not _is_safe_relative_path(path):
            return ToolResult(tool_id=call.tool_id, status="failed", summary="connector path is not allowed")
        url = urljoin(f"{self._definition.base_url}/", path.lstrip("/"))
        if not _host_allowed(url, self._definition.allowed_hosts):
            return ToolResult(tool_id=call.tool_id, status="failed", summary="connector host is not allowed")
        try:
            response = await self._transport(RestRequest(url=url, arguments=call.arguments))
        except Exception as exc:
            return ToolResult(tool_id=call.tool_id, status="failed", summary=f"connector failed: {type(exc).__name__}")
        if not _host_allowed(str(response.final_url), self._definition.allowed_hosts):
            return ToolResult(tool_id=call.tool_id, status="failed", summary="connector host is not allowed")
        return ToolResult(tool_id=call.tool_id, status="succeeded", summary=response.body[:1_000])


def _argument_value(arguments: tuple[ToolArgument, ...], name: str) -> str:
    for argument in arguments:
        if argument.name == name:
            return argument.value
    return ""


def _is_safe_relative_path(path: str) -> bool:
    parsed = urlparse(path)
    return bool(path.startswith("/")) and not parsed.scheme and not parsed.netloc and ".." not in parsed.path.split("/")


def _host_allowed(url: str, allowed_hosts: frozenset[str]) -> bool:
    host = (urlparse(url).hostname or "").lower()
    return host in allowed_hosts
