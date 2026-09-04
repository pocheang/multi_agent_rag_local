"""The single LangGraph topology used behind the public RAGPipeline facade."""

from __future__ import annotations

from typing import Any

from langgraph.graph import END, START, StateGraph

from app.core.config import Settings, get_settings
from app.orchestration.langgraph.nodes import WorkflowNodeRuntime, WorkflowServices
from app.orchestration.langgraph.state import OrchestrationGraphState
from app.orchestration.policies import ExecutionPolicy


def build_workflow(
    services: WorkflowServices,
    *,
    policy: ExecutionPolicy | None = None,
    settings: Settings | None = None,
    checkpointer: Any = None,
    monitor: Any = None,
):
    """Compile the bounded canonical workflow over injected typed services."""

    active_settings = settings or get_settings()
    runtime = WorkflowNodeRuntime(
        services=services,
        policy=policy or ExecutionPolicy(),
        max_verifier_retries=active_settings.verifier_max_retries,
        context_token_budget=active_settings.knowledge_context_token_budget,
        monitor=monitor,
    )
    graph = StateGraph(OrchestrationGraphState)
    graph.add_node("privacy_permission", runtime.privacy_permission)
    graph.add_node("router", runtime.router)
    graph.add_node("planner", runtime.planner)
    graph.add_node("knowledge", runtime.knowledge)
    graph.add_node("synthesizer", runtime.synthesizer)
    graph.add_node("verifier", runtime.verifier)
    graph.add_node("output_filter", runtime.output_filter)

    graph.add_edge(START, "privacy_permission")
    graph.add_edge("privacy_permission", "router")
    graph.add_conditional_edges(
        "router",
        runtime.after_router,
        {"planner": "planner", "knowledge": "knowledge"},
    )
    graph.add_edge("planner", "knowledge")
    graph.add_edge("knowledge", "synthesizer")
    graph.add_edge("synthesizer", "verifier")
    graph.add_conditional_edges(
        "verifier",
        runtime.after_verifier,
        {"knowledge": "knowledge", "output_filter": "output_filter"},
    )
    graph.add_edge("output_filter", END)
    return graph.compile(checkpointer=checkpointer, name="querymind_multimodal_knowledge_workflow")


def get_graph():
    """LangGraph Studio entry point using the canonical production services."""

    from app.orchestration.capabilities import build_orchestration_services

    return build_workflow(build_orchestration_services(), settings=get_settings())


__all__ = ["build_workflow", "get_graph"]
