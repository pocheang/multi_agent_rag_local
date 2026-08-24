"""Agent-decision and execution-trace evaluation helpers."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from app.domain.events import ExecutionEvent


def router_decision_score(predicted: Mapping[str, object], expected: Mapping[str, object]) -> dict[str, float]:
    fields = ("intent", "complexity", "completeness", "next_stage")
    scores = {
        field: float(str(predicted.get(field, "")) == str(expected.get(field, "")))
        for field in fields
        if field in expected
    }
    scores["overall"] = sum(scores.values()) / len(scores) if scores else 0.0
    return scores


def agent_trace_summary(events: Sequence[ExecutionEvent]) -> dict[str, object]:
    return {
        "stages": tuple(event.stage for event in events),
        "failed_stages": tuple(event.stage for event in events if event.status == "failed"),
        "total_latency_ms": sum(event.duration_ms for event in events),
        "retry_stage_count": max(0, sum(1 for event in events if event.stage == "verifier") - 1),
    }


__all__ = ["agent_trace_summary", "router_decision_score"]
