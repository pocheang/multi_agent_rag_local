"""Immutable contracts for the governed MCP boundary."""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from typing import Annotated, Literal
from uuid import uuid4

from pydantic import Field, HttpUrl, JsonValue, field_validator

from app.domain.contracts import ImmutableContract

ToolOperation = Literal["read", "write", "delete", "send", "charge"]
ToolRisk = Literal["read_only", "destructive", "idempotent", "open_world"]
ConnectorURL = Annotated[HttpUrl, Field(max_length=2_048)]
ConnectorHost = Annotated[str, Field(min_length=1, max_length=253)]


class ToolArgument(ImmutableContract):
    """One validated scalar argument supplied to a governed tool."""

    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    value: str = Field(max_length=8_000)


class ToolCall(ImmutableContract):
    """A tool invocation free of untyped parameter dictionaries."""

    tool_id: str = Field(pattern=r"^querymind_[a-z0-9]+(?:_[a-z0-9]+)+$")
    arguments: tuple[ToolArgument, ...] = Field(default_factory=tuple)
    approval_token: str | None = Field(default=None, min_length=24, max_length=256)
    execution_id: str = Field(default_factory=lambda: str(uuid4()), max_length=128)


class ToolParameter(ImmutableContract):
    """One declared, validated input to a governed tool.

    A typed contract rather than raw JSON Schema: everything else on this
    boundary is a pydantic model with ``extra="forbid"``, and a free-form schema
    dict would be the one place an unvalidated payload could enter.  It also
    keeps the catalogue the selector shows the model small enough to be exact.
    """

    name: str = Field(pattern=r"^[a-z][a-z0-9_]{0,63}$")
    description: str = Field(default="", max_length=400)
    required: bool = True
    max_length: int = Field(default=256, ge=1, le=8_000)
    pattern: str | None = Field(default=None, max_length=256)
    """Regex the supplied value must ``fullmatch``. The tightest gate available:
    tool arguments now originate from a model, not from a regex capture group
    with a shape baked into it."""


class ToolDefinition(ImmutableContract):
    """Registered tool policy, declared inputs, and execution limits."""

    tool_id: str = Field(pattern=r"^querymind_[a-z0-9]+(?:_[a-z0-9]+)+$")
    connector_id: str | None = Field(default=None, min_length=1, max_length=64)
    operation: ToolOperation
    risk: ToolRisk = "read_only"
    required_scopes: frozenset[str] = Field(default_factory=frozenset)
    timeout_seconds: int = Field(default=20, ge=1, le=120)
    description: str = Field(default="", max_length=400)
    """What the tool does, in the words the selector shows the model."""
    parameters: tuple[ToolParameter, ...] = Field(default_factory=tuple)

    def validation_error(self, arguments: tuple[ToolArgument, ...]) -> str | None:
        """Return why these arguments are unacceptable, or None if they are fine."""

        declared = {parameter.name: parameter for parameter in self.parameters}
        supplied: dict[str, str] = {}
        for argument in arguments:
            if argument.name in supplied:
                return f"duplicate argument: {argument.name}"
            if argument.name not in declared:
                return f"unknown argument: {argument.name}"
            supplied[argument.name] = argument.value
        for parameter in self.parameters:
            value = supplied.get(parameter.name)
            if value is None:
                if parameter.required:
                    return f"missing required argument: {parameter.name}"
                continue
            if len(value) > parameter.max_length:
                return f"argument too long: {parameter.name}"
            if parameter.pattern is not None and re.fullmatch(parameter.pattern, value) is None:
                return f"argument does not match its declared pattern: {parameter.name}"
        return None


class ApprovalRequest(ImmutableContract):
    """A single-use approval request for a high-risk tool call.

    Carries the approved ``arguments`` because resuming replays *this* call
    rather than asking the selector again. A model re-reading the same question
    is not guaranteed to produce the same call, and "the user approved that
    action" has to mean the action they were shown.
    """

    token: str = Field(default_factory=lambda: uuid4().hex + uuid4().hex)
    tool_id: str
    actor_id: str
    arguments: tuple[ToolArgument, ...] = Field(default_factory=tuple)
    call_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    expires_at: datetime = Field(default_factory=lambda: datetime.now(UTC) + timedelta(minutes=5))
    approved: bool = False
    approved_by: str | None = None
    consumed: bool = False


class ConnectorCredential(ImmutableContract):
    """Encrypted credential storage record; plaintext is never part of this model."""

    credential_id: str = Field(default_factory=lambda: str(uuid4()))
    connector_id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    encrypted_secret: str = Field(min_length=1)
    display_value: str = Field(min_length=3, max_length=32)


class ConnectorCredentialDisplay(ImmutableContract):
    """The only credential representation safe to return beyond the service boundary."""

    credential_id: str
    connector_id: str
    display_value: str = Field(min_length=3, max_length=32)


class ConnectorDefinition(ImmutableContract):
    """Safely configurable REST connector metadata."""

    connector_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,63}$")
    owner_id: str = Field(min_length=1)
    base_url: ConnectorURL
    allowed_hosts: frozenset[ConnectorHost] = Field(min_length=1, max_length=20)

    @field_validator("allowed_hosts")
    @classmethod
    def normalize_hosts(cls, hosts: frozenset[str]) -> frozenset[str]:
        normalized = frozenset(host.strip().lower() for host in hosts if host.strip())
        if not normalized:
            raise ValueError("allowed_hosts must contain at least one hostname")
        return normalized


class RestRequest(ImmutableContract):
    """One outbound REST request with redirect following explicitly disabled."""

    url: HttpUrl
    arguments: tuple[ToolArgument, ...] = Field(default_factory=tuple)
    follow_redirects: Literal[False] = False


class RestResponse(ImmutableContract):
    """Transport result with the final URL available for allowlist verification."""

    final_url: HttpUrl
    body: str = ""


class MCPAgentDescriptor(ImmutableContract):
    """A stable description of one read-only QueryMind RAG capability."""

    name: str = Field(min_length=1)
    purpose: str = Field(min_length=1)


class MCPConversationMessage(ImmutableContract):
    """One validated MCP conversation item forwarded to the RAG pipeline."""

    role: str = Field(min_length=1)
    content: str


class MCPRoute(ImmutableContract):
    """The route fields safe to publish from a pipeline result."""

    route: str
    reason: str = ""
    skill: str = ""
    agent_class: str = ""
    confidence: float | None = None


class MCPCitation(ImmutableContract):
    """A citation returned by a read-only MCP RAG query."""

    source: str
    content: str = ""
    document_id: str | None = None
    page: int | None = None
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class MCPDegradationEvent(ImmutableContract):
    """A safe degradation event returned by a read-only MCP RAG query."""

    stage: str
    reason: str
    fallback_used: bool = True
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class MCPRagResponse(ImmutableContract):
    """Structured response shared by every read-only MCP RAG tool."""

    answer: str
    route: MCPRoute
    citations: tuple[MCPCitation, ...] = Field(default_factory=tuple)
    quality_report: dict[str, JsonValue] = Field(default_factory=dict)
    degradation_events: tuple[MCPDegradationEvent, ...] = Field(default_factory=tuple)


class AuditRecord(ImmutableContract):
    """Secret-free record of one governed tool decision or execution."""

    tool_id: str
    connector_id: str | None = None
    actor_id: str
    approved_by: str | None = None
    argument_names: tuple[str, ...] = Field(default_factory=tuple)
    status: str
    execution_id: str | None = None
    duration_ms: int = Field(default=0, ge=0)
    summary: str = Field(default="", max_length=1_000)
