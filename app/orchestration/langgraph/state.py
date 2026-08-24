"""Runtime-only extensions to the canonical domain WorkflowState."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from app.domain.contracts import EvidenceBundle, FinalAnswer, RouteDecision, TaskPlan, ToolResult
from app.domain.events import ExecutionEvent
from app.domain.knowledge import AccessScope, KnowledgeStrategy
from app.domain.workflow import (
    CandidateAnswer,
    ClarificationResult,
    ContextBundle,
    RouterDecision,
    VerificationDecision,
    WorkflowError,
    WorkflowState,
)
from app.orchestration.request import OrchestrationRequest
from app.orchestration.timeout_control import ExecutionBudget
from app.privacy.models import PrivacyResult

# LangGraph resolves inherited TypedDict annotations with this module's globals.
# Keeping these names materialized prevents unresolved forward references while
# the domain module remains free of an orchestration import cycle.
_RUNTIME_TYPE_NAMES = (
    AccessScope,
    CandidateAnswer,
    ClarificationResult,
    ContextBundle,
    KnowledgeStrategy,
    OrchestrationRequest,
    PrivacyResult,
    RouterDecision,
    TaskPlan,
    VerificationDecision,
    WorkflowError,
)


class OrchestrationGraphState(WorkflowState, total=False):
    """Graph state with temporary legacy projections during incremental migration."""

    route: RouteDecision
    evidence_bundle: EvidenceBundle
    tool_results: tuple[ToolResult, ...]
    candidate: FinalAnswer
    budget: ExecutionBudget
    reporter: Callable[[ExecutionEvent], Awaitable[None]]


__all__ = ["OrchestrationGraphState"]
