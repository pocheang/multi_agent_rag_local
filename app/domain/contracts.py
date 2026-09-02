"""Immutable, validated values exchanged between orchestration stages."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import uuid4

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator

from app.domain.knowledge import EvidenceLayer, Modality

Intent = Literal["general_qa", "knowledge_retrieval", "web_search", "tool_call", "hybrid"]
Capability = Literal["rag", "web", "tool"]
ToolStatus = Literal["succeeded", "failed", "approval_required", "skipped"]
ApprovalStatus = Literal["not_required", "approved", "pending", "rejected"]


class RouterAction(StrEnum):
    """Router decision action for clarification flow."""

    CONTINUE = "CONTINUE"
    NEED_CLARIFICATION = "NEED_CLARIFICATION"


class ImmutableContract(BaseModel):
    """Base model that rejects extra fields and assignment after construction."""

    model_config = ConfigDict(extra="forbid", frozen=True)


class RouteDecision(ImmutableContract):
    """The typed outcome of selecting capabilities for one request."""

    intent: Intent = "knowledge_retrieval"
    # ``route`` is the execution-facing name.  ``intent`` remains the stable
    # semantic field used by existing callers.
    route: str | None = None
    confidence: float = Field(ge=0, le=1)
    # The pre-calibration confidence, carried only so the calibration loop can
    # attribute an outcome to the bucket that produced it. Feeding the calibrated
    # value back would train the calibrator on its own output.
    raw_confidence: float | None = Field(default=None, ge=0, le=1)
    # Fields the request is missing, if any. Deliberately *not* a route: what to
    # retrieve and whether to ask a question first are different decisions, and
    # collapsing them into `route="clarification"` threw away the router's answer
    # to the first one -- every comparison-shaped question lost graph and web.
    clarification_fields: tuple[str, ...] = Field(default_factory=tuple)
    requires_plan: bool
    allowed_capabilities: frozenset[Capability] = Field(default_factory=frozenset)
    reason: str = Field(min_length=1)

    @property
    def effective_route(self) -> str:
        return self.route or {
            "knowledge_retrieval": "vector",
            "general_qa": "vector",
            "web_search": "web",
            "tool_call": "react",
            "hybrid": "hybrid",
        }.get(self.intent, self.intent)


class TaskBudget(ImmutableContract):
    """Bounded execution budget for one planned task."""

    max_retrievals: int = Field(default=1, ge=0)
    max_tool_calls: int = Field(default=0, ge=0)


class PlannedTask(ImmutableContract):
    """One node in a planner-produced dependency DAG."""

    task_id: str = Field(min_length=1)
    prompt: str = Field(min_length=1)
    depends_on: tuple[str, ...] = Field(default_factory=tuple)
    parallel_group: str | None = None
    knowledge_required: bool = Field(
        default=True,
        validation_alias=AliasChoices("knowledge_required", "retrieval_required"),
    )
    tool_required: bool = False
    budget: TaskBudget = Field(default_factory=TaskBudget)

    @model_validator(mode="after")
    def reject_self_dependency(self) -> PlannedTask:
        if self.task_id in self.depends_on:
            raise ValueError("a task cannot depend on itself")
        return self

    @property
    def retrieval_required(self) -> bool:
        """Backward-compatible name for the canonical knowledge requirement."""

        return self.knowledge_required


class TaskPlan(ImmutableContract):
    """A validated task DAG that the orchestrator can execute or trace."""

    tasks: tuple[PlannedTask, ...] = Field(min_length=1)
    plan_fallback_reason: str | None = None

    @model_validator(mode="after")
    def validate_dependencies(self) -> TaskPlan:
        task_ids = {task.task_id for task in self.tasks}
        if len(task_ids) != len(self.tasks):
            raise ValueError("task ids must be unique")
        unknown_dependencies = {
            dependency for task in self.tasks for dependency in task.depends_on if dependency not in task_ids
        }
        if unknown_dependencies:
            raise ValueError("all task dependencies must be present in the plan")

        # Use Kahn's algorithm for cycle detection: O(V+E) instead of O(V²)
        # Build in-degree map: count incoming edges (dependencies pointing TO each task)
        in_degree = {task.task_id: len(task.depends_on) for task in self.tasks}

        # Start with nodes that have no dependencies (in-degree = 0)
        queue = [task_id for task_id, degree in in_degree.items() if degree == 0]
        processed = 0

        while queue:
            current = queue.pop(0)
            processed += 1
            # For each task that depends on the current task, reduce its in-degree
            for task in self.tasks:
                if current in task.depends_on:
                    in_degree[task.task_id] -= 1
                    if in_degree[task.task_id] == 0:
                        queue.append(task.task_id)

        # If we didn't process all nodes, there's a cycle
        if processed != len(self.tasks):
            raise ValueError("task dependencies must be acyclic")
        return self

    @property
    def requires_tools(self) -> bool:
        """Return whether at least one task requires a governed tool call."""
        return any(task.tool_required for task in self.tasks)

    @property
    def execution_layers(self) -> tuple[tuple[str, ...], ...]:
        """Return deterministic DAG ready sets for future parallel execution."""

        remaining = {task.task_id: set(task.depends_on) for task in self.tasks}
        layers: list[tuple[str, ...]] = []
        completed: set[str] = set()
        while remaining:
            ready = tuple(sorted(task_id for task_id, deps in remaining.items() if deps <= completed))
            if not ready:  # The model validator already rejects cycles.
                break
            layers.append(ready)
            completed.update(ready)
            for task_id in ready:
                remaining.pop(task_id)
        return tuple(layers)


class EvidenceItem(ImmutableContract):
    """One attributable fact or excerpt returned by a retriever."""

    item_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    content: str = Field(min_length=1)
    source: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    version: int | None = Field(default=None, ge=1)
    page: int | None = Field(default=None, ge=1)
    chunk_id: str | None = None
    image_id: str | None = None
    artifact_uri: str | None = None
    modality: Modality = "text"
    layer: EvidenceLayer = "evidence"
    acl_tags: frozenset[str] = Field(default_factory=frozenset)
    retriever: str = Field(default="unknown", min_length=1)
    score: float | None = Field(default=None, ge=0, le=1)
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    conflict_group: str | None = None

    @field_validator("source", "document_id", "retriever")
    @classmethod
    def require_nonblank_provenance(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("must not be blank")
        return value

    @model_validator(mode="after")
    def require_modality_provenance(self) -> EvidenceItem:
        if self.modality == "image" and not (self.image_id or "").strip():
            raise ValueError("image evidence requires image_id")
        return self


class EvidenceBundle(ImmutableContract):
    """The complete, immutable evidence set available to synthesis."""

    route: RouteDecision | None = None
    plan: TaskPlan | None = None
    items: tuple[EvidenceItem, ...] = Field(default_factory=tuple)
    citations: tuple[str, ...] = Field(default_factory=tuple)
    diagnostics: Mapping[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def derive_citations(self) -> EvidenceBundle:
        # Citation labels are added by the retriever or finalizer.  Returning
        # ``self`` keeps Pydantic's immutable-model validation semantics.
        return self

    @property
    def item_ids(self) -> tuple[str, ...]:
        """Expose evidence identifiers without leaking mutable collection state."""
        return tuple(item.item_id for item in self.items)


class ToolResult(ImmutableContract):
    """A safe, user-displayable outcome from one governed tool invocation."""

    tool_id: str = Field(min_length=1)
    status: ToolStatus
    approval_status: ApprovalStatus = "not_required"
    approval_token: str | None = Field(default=None, min_length=24, max_length=256)
    summary: str = ""
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple)


class FinalAnswer(ImmutableContract):
    """The citation-aware answer produced by the synthesis boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    answer: str = Field(default="", alias="text")
    citations: tuple[str, ...] = Field(default_factory=tuple)
    route: RouteDecision = Field(
        default_factory=lambda: RouteDecision(
            confidence=0.0,
            requires_plan=False,
            allowed_capabilities=frozenset(),
            reason="unresolved route",
        )
    )
    evidence: EvidenceBundle = Field(default_factory=EvidenceBundle)
    # The cited subset, in citation-number order: `cited_evidence[n - 1]` is what
    # `[n]` in the answer points at. Separate from `evidence`, which stays the
    # full authorized retrieval set -- collapsing the two made "retrieved
    # context" mean "whatever happened to be cited".
    cited_evidence: tuple[EvidenceItem, ...] = Field(default_factory=tuple)
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple)
    # Carried to the public boundary so a caller can see what ran -- and, when a
    # governed write is waiting on confirmation, that nothing ran yet.
    tool_results: tuple[ToolResult, ...] = Field(default_factory=tuple)
    unresolved_items: tuple[str, ...] = Field(default_factory=tuple)
    conflict_notes: tuple[str, ...] = Field(default_factory=tuple)
    execution_summary: str = ""
    grounding: Mapping[str, Any] = Field(default_factory=dict)
    safety: Mapping[str, Any] = Field(default_factory=dict)
    validation: ValidationStatus = Field(
        default_factory=lambda: ValidationStatus(
            state="degraded", approved=False, method="not_run", issues=("validation not run",)
        )
    )
    quality_report: OrchestratedQualityReport | None = None
    quality_card: Any = None  # AnswerQualityCard from user_experience module
    execution_metadata: Mapping[str, Any] = Field(default_factory=dict)

    @property
    def text(self) -> str:
        """Backward-compatible read-only name for the canonical answer field."""
        return self.answer


class ValidationStatus(ImmutableContract):
    """Fail-closed terminal validation state."""

    state: Literal["validated", "degraded", "rejected"]
    approved: bool
    method: str = Field(min_length=1)
    issues: tuple[str, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def reject_nonvalidated_approval(self) -> ValidationStatus:
        if self.state != "validated" and self.approved:
            raise ValueError("only validated status may be approved")
        return self


class OrchestratedQualityReport(ImmutableContract):
    """Small, stable quality report exposed by the typed terminal contract."""

    score: float = Field(default=0.0, ge=0, le=1)
    level: str = "unknown"
    details: Mapping[str, Any] = Field(default_factory=dict)


# Clarification-related contracts (mutable, for state management)


class ClarificationQuestion(BaseModel):
    """A clarification question to ask the user."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., description="The question to ask")
    options: list[str] = Field(default_factory=list, description="Predefined options (2-5)")
    allow_custom_input: bool = Field(default=True, description="Whether custom input is allowed")
    field_name: str = Field(..., description="Field name being clarified (e.g. 'scenario')")


class ClarificationContext(BaseModel):
    """Multi-round clarification context stored in session."""

    model_config = ConfigDict(extra="forbid")

    collected_info: dict[str, str] = Field(default_factory=dict, description="Collected information")
    asked_questions: list[str] = Field(default_factory=list, description="Asked field names")
    clarification_round: int = Field(default=0, description="Current round number")
    max_rounds: int = Field(default=10, description="Maximum rounds (dynamically set)")
    intent: str = Field(default="", description="Identified intent type")
    original_query: str = Field(default="", description="Query that owns this clarification state")


class EnhancedRouteDecision(ImmutableContract):
    """Enhanced route decision with clarification support.

    Wraps a RouteDecision and adds clarification-specific fields.
    Use base_decision to access the underlying RouteDecision fields.
    """

    # Core routing decision
    base_decision: RouteDecision

    # Clarification fields
    action: RouterAction = RouterAction.CONTINUE
    missing_information: tuple[str, ...] = Field(default_factory=tuple)
    clarification: ClarificationQuestion | None = None
    context: ClarificationContext = Field(default_factory=ClarificationContext)

    @property
    def intent(self) -> Intent:
        """Delegate to base decision."""
        return self.base_decision.intent

    @property
    def route(self) -> str | None:
        """Delegate to base decision."""
        return self.base_decision.route

    @property
    def confidence(self) -> float:
        """Delegate to base decision."""
        return self.base_decision.confidence

    @property
    def requires_plan(self) -> bool:
        """Delegate to base decision."""
        return self.base_decision.requires_plan

    @property
    def allowed_capabilities(self) -> frozenset[Capability]:
        """Delegate to base decision."""
        return self.base_decision.allowed_capabilities

    @property
    def reason(self) -> str:
        """Delegate to base decision."""
        return self.base_decision.reason

    @property
    def effective_route(self) -> str:
        """Delegate to base decision."""
        return self.base_decision.effective_route
