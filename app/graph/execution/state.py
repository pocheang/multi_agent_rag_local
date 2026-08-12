"""Declared execution-state shape retained for graph compatibility adapters."""

from __future__ import annotations

from typing import Any, TypedDict

from app.domain.contracts import EvidenceBundle, FinalAnswer, RouteDecision, TaskPlan, ValidationStatus
from app.orchestration.request import RetryBudget


class GraphState(TypedDict, total=False):
    execution_id: str
    request_id: str
    question: str
    session_id: str
    user_id: str | None
    memory_context: str
    use_web_fallback: bool
    use_reasoning: bool
    route: str
    route_decision: RouteDecision
    task_plan: TaskPlan | None
    retry_budget: RetryBudget
    adaptive_level: str
    adaptive_min_vector_hits: int
    adaptive_prefer_graph: bool
    adaptive_prefer_web: bool
    reason: str
    skill: str
    agent_class: str
    vector_result: dict[str, Any]
    graph_result: dict[str, Any]
    web_result: dict[str, Any]
    react_result: dict[str, Any]
    evidence: EvidenceBundle
    candidate_answer: str
    answer: str
    citations: list[dict[str, Any]]
    grounding: dict[str, Any]
    answer_safety: dict[str, Any]
    validation_status: ValidationStatus
    quality_report: dict[str, Any]
    final_answer: FinalAnswer
    execution_metadata: dict[str, Any]
    explainability: dict[str, Any]
    allowed_sources: list[str]
    agent_class_hint: str | None
    next_step: str
    retrieval_strategy: str | None
    force_language: str
    detected_language: str
    language_preference: str
