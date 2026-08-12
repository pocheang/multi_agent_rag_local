from typing import Any

from app.services.evidence_scoring import graph_evidence_score, vector_evidence_score


def build_explainability_report(state: dict[str, Any]) -> dict[str, Any]:
    vector_result = state.get("vector_result", {}) or {}
    graph_result = state.get("graph_result", {}) or {}
    web_result = state.get("web_result", {}) or {}
    route = str(state.get("route", "unknown"))
    report = {
        "route": route,
        "reason": str(state.get("reason", "")),
        "used_web": bool(web_result.get("used", False)),
        "vector_score": vector_evidence_score(vector_result),
        "graph_score": graph_evidence_score(graph_result),
        "vector_hits": int(vector_result.get("retrieved_count", 0) or 0),
        "vector_effective_hits": int(vector_result.get("effective_hit_count", 0) or 0),
        "graph_entities": len(graph_result.get("entities", []) or []),
        "graph_neighbors": len(graph_result.get("neighbors", []) or []),
        "retrieval_diagnostics": vector_result.get("retrieval_diagnostics", {}),
        "grounding": state.get("grounding", {}),
        "answer_safety": state.get("answer_safety", {}),
    }
    if report["used_web"]:
        report["decision_summary"] = "local_evidence_insufficient_then_web_fallback"
    else:
        report["decision_summary"] = "local_evidence_sufficient_no_web"
    return report
