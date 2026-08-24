"""Safe terminal diagnostics derived from canonical LangGraph state."""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from typing import Any

from app.domain.events import ExecutionEvent


def summarize_workflow_execution(state: Mapping[str, Any]) -> dict[str, Any]:
    events = tuple(event for event in state.get("trace", ()) if isinstance(event, ExecutionEvent))
    stage_latency: dict[str, int] = defaultdict(int)
    stage_status: dict[str, str] = {}
    invocations: Counter[str] = Counter()
    failures: list[dict[str, str]] = []
    for event in events:
        invocations[event.stage] += 1
        stage_latency[event.stage] += event.duration_ms
        stage_status[event.stage] = event.status
        metadata = {item.key: item.value for item in event.metadata}
        reason = metadata.get("failure_reason")
        if event.status == "failed" or reason:
            failures.append({"stage": event.stage, "reason": reason or event.message or "stage_failed"})

    route = state.get("route_decision")
    strategy = state.get("knowledge_strategy")
    verification = state.get("verification")
    evidence = state.get("evidence_bundle")
    router_decision = (
        {
            "intent": route.intent,
            "complexity": route.complexity,
            "completeness": route.completeness,
            "next_stage": route.next_stage,
            "confidence": route.confidence,
            "reason": route.reason,
        }
        if route is not None
        else None
    )
    selected_sources = tuple(source.source for source in strategy.sources) if strategy is not None else ()
    knowledge_diagnostics = dict(evidence.diagnostics) if evidence is not None else {}
    return {
        "stage_latency_ms": dict(stage_latency),
        "stage_invocations": dict(invocations),
        "stage_status": stage_status,
        "total_stage_latency_ms": sum(stage_latency.values()),
        "retry_count": int(state.get("retry_count", 0) or 0),
        "failure_reasons": tuple(failures),
        "router_decision": router_decision,
        "selected_knowledge_sources": selected_sources,
        "verification_status": getattr(verification, "status", None),
        "knowledge_diagnostics": knowledge_diagnostics,
        "token_usage": _token_usage(state),
    }


def _token_usage(state: Mapping[str, Any]) -> dict[str, Any]:
    raw = state.get("token_usage")
    if isinstance(raw, Mapping):
        return {
            "available": True,
            "input_tokens": _optional_int(raw.get("input_tokens")),
            "output_tokens": _optional_int(raw.get("output_tokens")),
            "total_tokens": _optional_int(raw.get("total_tokens")),
        }
    request = state.get("request")
    evidence = state.get("evidence_bundle")
    answer = state.get("final_answer")
    estimated_input = _estimate_tokens(
        "\n".join(
            (
                str(getattr(request, "question", "") or ""),
                "\n".join(item.content for item in getattr(evidence, "items", ()) or ()),
            )
        )
    )
    estimated_output = _estimate_tokens(str(getattr(answer, "answer", "") or ""))
    return {
        "available": False,
        "input_tokens": None,
        "output_tokens": None,
        "total_tokens": None,
        "reason": "model_provider_did_not_report_usage",
        "estimated_input_tokens": estimated_input,
        "estimated_output_tokens": estimated_output,
        "estimated_total_tokens": estimated_input + estimated_output,
    }


def _optional_int(value: object) -> int | None:
    try:
        return max(0, int(value)) if value is not None else None
    except (TypeError, ValueError):
        return None


def _estimate_tokens(value: str) -> int:
    return max(0, (len(str(value or "")) + 3) // 4)


__all__ = ["summarize_workflow_execution"]
