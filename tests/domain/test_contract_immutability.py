"""Contract-wide regression coverage for immutable, closed schemas."""

import pytest
from pydantic import ValidationError

from app.domain.contracts import (
    EvidenceBundle,
    EvidenceItem,
    FinalAnswer,
    PlannedTask,
    RouteDecision,
    TaskPlan,
    ToolResult,
)
from app.domain.events import ExecutionEvent


def _route() -> RouteDecision:
    return RouteDecision(
        intent="knowledge_retrieval",
        confidence=0.9,
        requires_plan=False,
        allowed_capabilities=frozenset({"rag"}),
        reason="Direct lookup.",
    )


@pytest.mark.parametrize(
    ("contract", "field"),
    [
        (_route(), "reason"),
        (TaskPlan(tasks=(PlannedTask(task_id="retrieve", prompt="Retrieve"),)), "tasks"),
        (EvidenceBundle(items=(EvidenceItem(content="Fact", source="guide", document_id="guide"),)), "items"),
        (ToolResult(tool_id="querymind_rag_search_evidence", status="succeeded"), "status"),
        (FinalAnswer(text="Fact", route=_route()), "text"),
        (ExecutionEvent(stage="route", status="completed"), "stage"),
    ],
)
def test_domain_contracts_reject_reassignment_and_extra_fields(contract: object, field: str) -> None:
    """Removing frozen/forbid settings from any public contract must fail this test."""
    with pytest.raises(ValidationError):
        setattr(contract, field, getattr(contract, field))

    payload = {**contract.model_dump(mode="json"), "unexpected": True}  # type: ignore[attr-defined]
    with pytest.raises(ValidationError):
        contract.__class__.model_validate(payload)  # type: ignore[attr-defined]
