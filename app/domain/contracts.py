"""Immutable, validated values exchanged between orchestration stages."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

Intent = Literal["general_qa", "knowledge_retrieval", "web_search", "tool_call", "hybrid"]
Capability = Literal["rag", "web", "tool"]
ToolStatus = Literal["succeeded", "failed", "approval_required", "skipped"]
ApprovalStatus = Literal["not_required", "approved", "pending", "rejected"]


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
    retrieval_required: bool = True
    tool_required: bool = False
    budget: TaskBudget = Field(default_factory=TaskBudget)

    @model_validator(mode="after")
    def reject_self_dependency(self) -> PlannedTask:
        if self.task_id in self.depends_on:
            raise ValueError("a task cannot depend on itself")
        return self


class TaskPlan(ImmutableContract):
    """A validated task DAG that the orchestrator can execute or trace."""

    tasks: tuple[PlannedTask, ...] = Field(min_length=1)

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
        dependencies = {task.task_id: task.depends_on for task in self.tasks}
        visiting: set[str] = set()
        visited: set[str] = set()

        def has_cycle(task_id: str) -> bool:
            if task_id in visiting:
                return True
            if task_id in visited:
                return False
            visiting.add(task_id)
            cycle_found = any(has_cycle(dependency) for dependency in dependencies[task_id])
            visiting.remove(task_id)
            visited.add(task_id)
            return cycle_found

        if any(has_cycle(task_id) for task_id in dependencies):
            raise ValueError("task dependencies must be acyclic")
        return self

    @property
    def requires_tools(self) -> bool:
        """Return whether at least one task requires a governed tool call."""
        return any(task.tool_required for task in self.tasks)


class EvidenceItem(ImmutableContract):
    """One attributable fact or excerpt returned by a retriever."""

    item_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    content: str = Field(min_length=1)
    source: str = Field(min_length=1)
    document_id: str = Field(min_length=1)
    page: int | None = Field(default=None, ge=1)
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
    evidence_ids: tuple[str, ...] = Field(default_factory=tuple)
    unresolved_items: tuple[str, ...] = Field(default_factory=tuple)
    conflict_notes: tuple[str, ...] = Field(default_factory=tuple)
    execution_summary: str = ""
    grounding: Mapping[str, Any] = Field(default_factory=dict)
    safety: Mapping[str, Any] = Field(default_factory=dict)
    validation: ValidationStatus = Field(default_factory=lambda: ValidationStatus(
        state="degraded", approved=False, method="not_run", issues=("validation not run",)
    ))
    quality_report: OrchestratedQualityReport | None = None
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
