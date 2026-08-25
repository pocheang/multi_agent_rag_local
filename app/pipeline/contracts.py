"""Immutable input and normalized output contracts for the unified RAG pipeline.

The contracts are intentionally standalone during the migration.  They model
the data passed between adapters without invoking existing agents or changing
any API route.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Any

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
    retrieval_strategy: str | None = None
    use_reasoning: bool = False
    use_web_fallback: bool = False
    deadline_at: datetime | None = None
    enable_decomposition: bool = False
    enable_self_rag: bool = False
    enable_context_tracking: bool = True
    force_language: str = ""
    request_id: str | None = None
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
        retrieval_strategy=request.retrieval_strategy,
        use_reasoning=request.use_reasoning,
        use_web_fallback=request.use_web_fallback,
        deadline_at=request.deadline_at,
        enable_decomposition=request.enable_decomposition,
        enable_self_rag=request.enable_self_rag,
        enable_context_tracking=request.enable_context_tracking,
        force_language=request.force_language,
        request_id=request.request_id,
        runtime_context=request.runtime_context,
    )


class PipelineCitation(BaseModel):
    """A source citation normalized for pipeline results."""

    model_config = ConfigDict(extra="forbid")

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


class PipelineResult(BaseModel):
    """Normalized result produced by the future unified execution pipeline."""

    model_config = ConfigDict(extra="forbid")

    answer: str
    citations: tuple[PipelineCitation, ...] = Field(default_factory=tuple)
    route: PipelineRoute
    contexts: tuple[PipelineContext, ...] = Field(default_factory=tuple)
    quality_report: dict[str, Any] = Field(default_factory=dict)
    execution_metadata: dict[str, Any] = Field(default_factory=dict)
    degradation_events: tuple[DegradationEvent, ...] = Field(default_factory=tuple)
