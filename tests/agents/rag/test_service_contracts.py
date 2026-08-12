"""Contract tests for typed retriever selection and legacy evidence normalization."""

import pytest

from app.agents.rag.service import RAGAgentService, _bundle_from_legacy_payload
from app.domain.contracts import EvidenceBundle, EvidenceItem, PlannedTask, RouteDecision, TaskBudget, TaskPlan
from app.orchestration.request import OrchestrationRequest


@pytest.mark.asyncio
async def test_rag_service_uses_plan_prompt_and_only_enabled_retrievers() -> None:
    """Ignoring a task's retrieval flag or prompt would violate the typed plan contract."""
    calls: list[tuple[str, str]] = []

    def retriever(name: str):
        async def run(request: OrchestrationRequest, *_args: object) -> EvidenceBundle:
            calls.append((name, request.question))
            return EvidenceBundle(
                items=(EvidenceItem(content=name, source=name, document_id=name, score=0.5),)
            )

        return run

    plan = TaskPlan(
        tasks=(
            PlannedTask(task_id="retrieve", prompt="planned evidence query", budget=TaskBudget(max_retrievals=3)),
            PlannedTask(
                task_id="skip",
                prompt="must not be retrieved",
                retrieval_required=False,
                budget=TaskBudget(max_retrievals=0),
            ),
        )
    )
    route = RouteDecision(
        intent="hybrid",
        confidence=0.9,
        requires_plan=True,
        allowed_capabilities=frozenset({"rag"}),
        reason="comparison",
    )

    evidence = await RAGAgentService(
        vector=retriever("vector"),
        bm25=retriever("bm25"),
        graph=retriever("graph"),
    ).retrieve(OrchestrationRequest(question="original question"), route, plan)

    assert set(calls) == {
        ("vector", "planned evidence query"),
        ("bm25", "planned evidence query"),
        ("graph", "planned evidence query"),
    }
    assert {item.document_id for item in evidence.items} == {"vector", "bm25", "graph"}


@pytest.mark.asyncio
async def test_rag_service_limits_each_planned_task_to_its_retrieval_budget() -> None:
    """Treating max_retrievals as a boolean would exceed the plan's execution budget."""
    calls: list[str] = []

    def retriever(name: str):
        async def run(*_args: object) -> EvidenceBundle:
            calls.append(name)
            return EvidenceBundle()

        return run

    plan = TaskPlan(
        tasks=(PlannedTask(task_id="retrieve", prompt="planned", budget=TaskBudget(max_retrievals=1)),)
    )
    route = RouteDecision(
        intent="hybrid",
        confidence=0.9,
        requires_plan=True,
        allowed_capabilities=frozenset({"rag"}),
        reason="comparison",
    )

    await RAGAgentService(
        vector=retriever("vector"), bm25=retriever("bm25"), graph=retriever("graph")
    ).retrieve(OrchestrationRequest(question="original"), route, plan)

    assert calls == ["vector"]


def test_legacy_evidence_normalization_keeps_nested_pages_and_graph_context() -> None:
    """Discarding nested citation provenance or graph context loses real retrieval evidence."""
    vector = _bundle_from_legacy_payload(
        {
            "citations": [
                {
                    "source": "guide.pdf",
                    "content": "first page",
                    "metadata": {"document_id": "guide", "page": 1, "rerank_score": 0.7},
                },
                {
                    "source": "guide.pdf",
                    "content": "second page",
                    "metadata": {"document_id": "guide", "page": 2, "rerank_score": 0.8},
                },
            ]
        },
        "vector",
    )
    graph = _bundle_from_legacy_payload(
        {"context": "Transformer USES Attention", "entities": ["Transformer"], "graph_signal_score": 0.8},
        "graph",
        fallback_document_id="graph:transformer",
    )

    assert {(item.document_id, item.page) for item in vector.items} == {("guide", 1), ("guide", 2)}
    assert graph.items[0].source == "knowledge_graph"
    assert graph.items[0].content == "Transformer USES Attention"

