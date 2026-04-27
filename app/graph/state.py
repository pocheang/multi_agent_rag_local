from typing import Any, TypedDict


class GraphState(TypedDict, total=False):
    question: str
    memory_context: str
    use_web_fallback: bool
    use_reasoning: bool
    route: str
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
    answer: str
    grounding: dict[str, Any]
    answer_safety: dict[str, Any]
    explainability: dict[str, Any]
    allowed_sources: list[str]
    agent_class_hint: str | None
    next_step: str
    retrieval_strategy: str | None
