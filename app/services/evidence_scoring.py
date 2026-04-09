from typing import Any


def vector_evidence_score(vector_result: dict[str, Any]) -> float:
    if not isinstance(vector_result, dict):
        return 0.0
    effective_hits = float(vector_result.get("effective_hit_count", vector_result.get("retrieved_count", 0)) or 0)
    return min(1.0, effective_hits / 3.0)


def graph_evidence_score(graph_result: dict[str, Any]) -> float:
    if not isinstance(graph_result, dict):
        return 0.0
    explicit_signal = graph_result.get("graph_signal_score")
    if isinstance(explicit_signal, (int, float)):
        return min(1.0, max(0.0, float(explicit_signal)))
    entity_count = len(graph_result.get("entities", []) or [])
    neighbor_count = len(graph_result.get("neighbors", []) or [])
    return min(1.0, (entity_count / 3.0) + (neighbor_count / 12.0))


def local_evidence_score(vector_result: dict[str, Any], graph_result: dict[str, Any], route: str) -> float:
    v = vector_evidence_score(vector_result)
    g = graph_evidence_score(graph_result)
    if route == "vector":
        return v
    if route == "graph":
        return g
    if route == "hybrid":
        return min(1.0, 0.7 * v + 0.3 * g)
    return max(v, g)


def evidence_is_sufficient(
    vector_result: dict[str, Any],
    graph_result: dict[str, Any],
    route: str,
    min_hits: int,
) -> bool:
    # Map old "min hits" semantics into normalized evidence threshold.
    if min_hits <= 1:
        threshold = 0.34
    elif min_hits == 2:
        threshold = 0.55
    else:
        threshold = 0.72
    return local_evidence_score(vector_result, graph_result, route=route) >= threshold
