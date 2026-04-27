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
    # Check for execution failures first
    vector_failed = vector_result.get("error") or vector_result.get("timeout")
    graph_failed = graph_result.get("error") or graph_result.get("timeout")

    # If both sources failed, evidence is insufficient
    if route == "hybrid" and vector_failed and graph_failed:
        return False

    # If single source failed, evidence is insufficient
    if route == "vector" and vector_failed:
        return False
    if route == "graph" and graph_failed:
        return False

    score = local_evidence_score(vector_result, graph_result, route=route)

    # Progressive threshold based on min_hits requirement
    # Align thresholds to actually meet min_hits (score = hits / 3.0)
    if min_hits <= 1:
        threshold = 0.33  # ~1.0 effective hit
    elif min_hits == 2:
        threshold = 0.67  # ~2.0 effective hits
    elif min_hits == 3:
        threshold = 1.0   # ~3.0 effective hits
    else:
        threshold = 1.0   # ~3.0+ effective hits (capped at 1.0)

    # For hybrid route, be more lenient if either vector or graph has strong signal
    if route == "hybrid":
        v_score = vector_evidence_score(vector_result)
        g_score = graph_evidence_score(graph_result)
        # If either source is strong, lower the combined threshold moderately
        if v_score >= 0.67 or g_score >= 0.67:
            threshold = max(0.5, threshold - 0.2)

    return score >= threshold
