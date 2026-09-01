"""Immutable input and normalized output contracts for the unified RAG pipeline.

The contracts are intentionally standalone during the migration.  They model
the data passed between adapters without invoking existing agents or changing
any API route.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.pipeline.profiles import PipelineProfile

if TYPE_CHECKING:
    from app.orchestration.request import OrchestrationRequest


class _ImmutableContract(BaseModel):
    """Base class for request-side values that cannot be reassigned."""

    model_config = ConfigDict(frozen=True, extra="forbid")


class ConversationMessage(_ImmutableContract):
    """A compact, immutable conversation item supplied with a request."""

    role: str = Field(min_length=1)
    content: str


class PipelineUser(_ImmutableContract):
    """Identity and authorization data needed by downstream adapters."""

    user_id: str | None = None
    tenant_id: str | None = None
    username: str | None = None
    role: str | None = None
    permissions: frozenset[str] = Field(default_factory=frozenset)


class SourceScope(_ImmutableContract):
    """Authorized source and document filters for a single request."""

    allowed_sources: frozenset[str] | None = None
    document_ids: frozenset[str] | None = None
    acl_tags: frozenset[str] | None = None
    allowed_fields: frozenset[str] | None = None
    agent_class_hint: str | None = None


class PipelineRequest(_ImmutableContract):
    """The complete, immutable input to a future ``RAGPipeline.execute`` call.

    Advanced-only capabilities are request-level opt-ins.  Their default values
    intentionally match the current Advanced RAG endpoint and do not silently
    enable query decomposition or Self-RAG.
    """

    question: str = Field(min_length=1)
    profile: PipelineProfile
    session_id: str | None = None
    conversation: tuple[ConversationMessage, ...] = Field(default_factory=tuple)
    user: PipelineUser | None = None
    source_scope: SourceScope = Field(default_factory=SourceScope)
    use_reasoning: bool = False
    use_web_fallback: bool = False
    deadline_at: datetime | None = None
    enable_decomposition: bool = False
    enable_self_rag: bool = False
    enable_context_tracking: bool = True
    force_language: str = ""
    # Set on a resume: the run replays the tool call the user approved instead
    # of asking the selector again.
    approval_token: str | None = Field(default=None, min_length=24, max_length=256)
    request_id: str | None = None
    # Ties the stage events this run emits to the trace the caller already
    # opened, so GET /api/v1/orchestration/executions/{id}/events finds them.
    execution_id: str | None = None
    runtime_context: Any | None = Field(default=None, exclude=True)

    @property
    def actor(self) -> PipelineUser | None:
        """Expose the request identity through the orchestration-neutral actor view.

        Shadow observation accepts an orchestration-owned structural protocol.
        Keeping this alias on the public contract preserves existing callers
        without making orchestration depend on ``PipelineRequest``.
        """
        return self.user


def to_orchestration_request(request: PipelineRequest) -> OrchestrationRequest:
    """Translate the public request contract before entering orchestration.

    This is deliberately owned by the pipeline boundary: orchestration receives
    only its own immutable request model and never imports public pipeline
    fields or types.
    """
    from app.orchestration.request import (
        ConversationTurn,
        OrchestrationRequest,
        RequestActor,
        RequestScope,
    )

    return OrchestrationRequest(
        question=request.question,
        profile=request.profile.value,
        session_id=request.session_id,
        conversation=tuple(ConversationTurn(role=item.role, content=item.content) for item in request.conversation),
        actor=(
            RequestActor(
                user_id=request.user.user_id,
                tenant_id=request.user.tenant_id or request.user.user_id,
                username=request.user.username,
                role=request.user.role,
                permissions=request.user.permissions,
            )
            if request.user
            else None
        ),
        source_scope=RequestScope(
            allowed_sources=request.source_scope.allowed_sources,
            document_ids=request.source_scope.document_ids,
            acl_tags=request.source_scope.acl_tags,
            allowed_fields=request.source_scope.allowed_fields,
            agent_class_hint=request.source_scope.agent_class_hint,
        ),
        use_reasoning=request.use_reasoning,
        use_web_fallback=request.use_web_fallback,
        deadline_at=request.deadline_at,
        enable_decomposition=request.enable_decomposition,
        enable_self_rag=request.enable_self_rag,
        enable_context_tracking=request.enable_context_tracking,
        force_language=request.force_language,
        approval_token=request.approval_token,
        request_id=request.request_id,
        execution_id=request.execution_id,
        runtime_context=request.runtime_context,
    )


class PipelineCitation(BaseModel):
    """A source citation normalized for pipeline results."""

    model_config = ConfigDict(extra="forbid")

    # The reader-facing marker ("[1]") this citation carries in the answer text.
    # Set only on the numbered path; a caller that parses bare citation labels
    # has no answer text to have numbered against.
    marker: str | None = None
    source: str
    content: str = ""
    document_id: str | None = None
    version: int | None = Field(default=None, ge=1)
    page: int | None = None
    chunk_id: str | None = None
    image_id: str | None = None
    artifact_uri: str | None = None
    modality: str | None = None
    layer: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PipelineContext(BaseModel):
    """A retrieved context normalized for pipeline results."""

    model_config = ConfigDict(extra="forbid")

    content: str
    source: str | None = None
    document_id: str | None = None
    version: int | None = Field(default=None, ge=1)
    page: int | None = Field(default=None, ge=1)
    chunk_id: str | None = None
    image_id: str | None = None
    artifact_uri: str | None = None
    modality: str | None = None
    layer: str | None = None
    score: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class PipelineRoute(BaseModel):
    """The route decision shared by every API compatibility adapter."""

    model_config = ConfigDict(extra="forbid")

    route: str
    reason: str = ""
    skill: str = ""
    agent_class: str = ""
    confidence: float | None = None


class DegradationEvent(BaseModel):
    """A structured fallback or degradation applied while serving a request."""

    model_config = ConfigDict(extra="forbid")

    stage: str
    reason: str
    fallback_used: bool = True
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolRunView(BaseModel):
    """One governed tool invocation, as the caller may see it.

    Without this the multi-step loop is invisible: a request that ran two tools
    produced one answer and no record of what happened. Carries no approval
    token -- that belongs to `PipelineResult.pending_approval`, which is the
    single place a client should look for an action it can confirm.
    """

    model_config = ConfigDict(extra="forbid")

    tool_id: str
    status: str
    summary: str = ""


class PendingApproval(BaseModel):
    """A governed action the run produced but did not perform.

    Its presence is the whole reason ``PipelineResult.status`` exists: the run
    completed normally and produced an answer, but the action the user asked
    for is waiting on their confirmation.
    """

    model_config = ConfigDict(extra="forbid")

    tool_id: str
    token: str
    summary: str = ""


class PipelineResult(BaseModel):
    """Normalized result produced by the future unified execution pipeline."""

    model_config = ConfigDict(extra="forbid")

    # A discriminator rather than a separate response shape or a 202: the run
    # *did* complete and the answer *is* the answer. Only the governed action
    # is outstanding, and a caller that ignores this field still behaves
    # correctly -- it just will not offer the confirmation.
    status: Literal["complete", "pending_approval"] = "complete"
    pending_approval: PendingApproval | None = None
    tool_runs: tuple[ToolRunView, ...] = Field(default_factory=tuple)
    answer: str
    citations: tuple[PipelineCitation, ...] = Field(default_factory=tuple)
    route: PipelineRoute
    contexts: tuple[PipelineContext, ...] = Field(default_factory=tuple)
    quality_report: dict[str, Any] = Field(default_factory=dict)
    execution_metadata: dict[str, Any] = Field(default_factory=dict)
    degradation_events: tuple[DegradationEvent, ...] = Field(default_factory=tuple)
