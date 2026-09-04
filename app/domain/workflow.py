"""Canonical structured values shared by the LangGraph workflow."""

from __future__ import annotations

import operator
from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, Annotated, Any, Literal, Protocol, TypedDict

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.domain.contracts import (
    ClarificationContext,
    ClarificationQuestion,
    EvidenceItem,
    FinalAnswer,
    TaskPlan,
)
from app.domain.events import ExecutionEvent
from app.domain.knowledge import AccessScope, EvidenceRef, KnowledgeSource, KnowledgeStrategy, MemoryItem

if TYPE_CHECKING:
    from app.orchestration.request import OrchestrationRequest
    from app.privacy.models import PrivacyResult


class ImmutableWorkflowContract(BaseModel):
    """Base contract for immutable workflow state values."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RouterDecision(ImmutableWorkflowContract):
    """Execution-facing Router output, separate from retrieval execution."""

    intent: str = Field(min_length=1)
    complexity: Literal["simple", "complex"]
    completeness: Literal["complete", "incomplete", "ambiguous"]
    next_stage: Literal["planner", "knowledge"]
    knowledge_hints: frozenset[KnowledgeSource] = Field(default_factory=frozenset)
    confidence: float = Field(ge=0, le=1)
    reason: str = Field(min_length=1)


class ClarificationResult(ImmutableWorkflowContract):
    """One resumable clarification outcome with an optional complete query."""

    action: Literal["ask", "continue", "skipped"]
    question: ClarificationQuestion | None = None
    context: ClarificationContext
    complete_query: str | None = None
    workflow_thread_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_action_payload(self) -> ClarificationResult:
        if self.action == "ask" and self.question is None:
            raise ValueError("ask requires a clarification question")
        if self.action == "continue" and not (self.complete_query or "").strip():
            raise ValueError("continue requires complete_query")
        return self


class ContextBundle(ImmutableWorkflowContract):
    """Authorized, fused evidence plus its rendered prompt representation."""

    evidence: tuple[EvidenceItem, ...] = Field(default_factory=tuple)
    rendered_context: str = ""
    diagnostics: dict[str, Any] = Field(default_factory=dict)


class CandidateAnswer(ImmutableWorkflowContract):
    """Synthesizer output before deterministic filtering and verification."""

    text: str
    citations: tuple[EvidenceRef, ...] = Field(default_factory=tuple)
    unresolved_items: tuple[str, ...] = Field(default_factory=tuple)


class WorkflowError(ImmutableWorkflowContract):
    """A trace-safe stage failure without raw sensitive payloads."""

    stage: str = Field(min_length=1)
    code: str = Field(min_length=1)
    retryable: bool = False
    fallback_used: bool = False


class VerificationDecision(ImmutableWorkflowContract):
    """Bounded Verifier outcome used by the graph's only retry edge."""

    status: Literal["approved", "retry_retrieval", "rejected", "degraded"]
    unsupported_claims: tuple[str, ...] = Field(default_factory=tuple)
    citation_errors: tuple[str, ...] = Field(default_factory=tuple)
    conflicts: tuple[str, ...] = Field(default_factory=tuple)
    missing_aspects: tuple[str, ...] = Field(default_factory=tuple)
    retry_query: str | None = None

    @model_validator(mode="after")
    def require_retry_query(self) -> VerificationDecision:
        if self.status == "retry_retrieval" and not (self.retry_query or "").strip():
            raise ValueError("retry_retrieval requires retry_query")
        return self


class WorkflowState(TypedDict, total=False):
    """Typed state passed between LangGraph nodes."""

    request: OrchestrationRequest
    privacy: PrivacyResult
    permission_scope: AccessScope
    route_decision: RouterDecision
    task_plan: TaskPlan
    knowledge_strategy: KnowledgeStrategy
    context: ContextBundle
    candidate_answer: CandidateAnswer
    verification: VerificationDecision
    final_answer: FinalAnswer
    retry_count: int
    errors: Annotated[tuple[WorkflowError, ...], operator.add]
    trace: Annotated[tuple[ExecutionEvent, ...], operator.add]


class KnowledgeAgentPort(Protocol):
    """Knowledge strategy boundary; implementations must not retrieve."""

    async def decide(
        self,
        request: OrchestrationRequest,
        route: RouterDecision,
        plan: TaskPlan | None,
        retry_feedback: VerificationDecision | None = None,
    ) -> KnowledgeStrategy: ...


class KnowledgeOrchestratorPort(Protocol):
    """Ordinary service boundary that executes a KnowledgeStrategy."""

    async def retrieve(
        self,
        strategy: KnowledgeStrategy,
        scope: AccessScope,
        trace: Callable[[ExecutionEvent], Awaitable[None]],
    ) -> ContextBundle: ...


class LongTermMemoryPort(Protocol):
    """Provider-neutral governed long-term memory boundary."""

    async def search(self, query: str, scope: AccessScope, top_k: int) -> Sequence[MemoryItem]: ...

    async def upsert(self, item: MemoryItem, scope: AccessScope) -> MemoryItem: ...

    async def expire(self, memory_id: str, scope: AccessScope) -> bool: ...


__all__ = [
    "CandidateAnswer",
    "ClarificationResult",
    "ContextBundle",
    "ImmutableWorkflowContract",
    "KnowledgeAgentPort",
    "KnowledgeOrchestratorPort",
    "LongTermMemoryPort",
    "RouterDecision",
    "VerificationDecision",
    "WorkflowError",
    "WorkflowState",
]
