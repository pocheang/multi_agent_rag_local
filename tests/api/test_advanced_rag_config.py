"""Every value /api/advanced-rag/config reports comes from what actually gates it.

This endpoint has been wrong three times for the same reason: a plausible-looking
switch was read instead of the real one, and nothing checked. The 2026-09-01 pass
corrected two of the three keys and left `self_rag.enabled_by_default` pointing at
`VectorRAGConfig.enable_evaluation` -- which gated a placeholder that reported
`evaluated_count` without evaluating, behind an evaluator the agent's only
construction site never supplied a client for.

So these tests assert the *link*, not the value: change the thing that gates the
feature and the reported value follows. A test that asserted `false == false`
would have passed throughout.
"""

from __future__ import annotations

import asyncio

import pytest

from app.agents.shared.config import VectorRAGConfig
from app.api.routes.public import query as query_module


def _config() -> dict:
    return asyncio.run(query_module.get_config())


def test_query_decomposition_follows_the_setting_that_gates_it(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = query_module.get_settings()

    for enabled in (True, False):
        monkeypatch.setattr(settings, "query_decompose_enabled", enabled)
        assert _config()["query_decomposition"]["enabled_by_default"] is enabled


def test_the_sub_query_bound_reported_is_the_one_the_decomposer_enforces() -> None:
    from app.services.query.decomposer import QueryDecomposer

    reported = _config()["query_decomposition"]["max_sub_queries"]

    # The bound the decomposer truncates with, not an environment variable that
    # merely sounds like it -- which is what this key used to report.
    assert QueryDecomposer(llm_client=None).max_sub_queries == reported


def test_self_rag_reports_the_request_flag_that_actually_turns_it_on() -> None:
    """`enable_self_rag` on the request is the switch; nothing else is."""

    declared = query_module.AdvancedRAGRequest.model_fields["enable_self_rag"].default

    assert _config()["self_rag"]["enabled_by_default"] is bool(declared)


def test_the_reported_thresholds_are_the_ones_the_evaluator_applies(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.services.retrieval.self_rag_evaluator import SelfRAGEvaluator

    settings = query_module.get_settings()
    monkeypatch.setattr(settings, "self_rag_relevance_threshold", 0.31)
    monkeypatch.setattr(settings, "self_rag_quality_threshold", 0.87)

    reported = _config()["self_rag"]
    evaluator = SelfRAGEvaluator(llm_client=None)

    assert reported["relevance_threshold"] == pytest.approx(evaluator.relevance_threshold)
    assert reported["quality_threshold"] == pytest.approx(evaluator.quality_threshold)


def test_the_switch_that_gated_nothing_is_gone() -> None:
    """A field whose only reader was this page is not configuration, it is decoration."""

    assert "enable_evaluation" not in VectorRAGConfig.model_fields


def test_the_vector_agent_carries_no_evaluation_stub() -> None:
    """It returned "evaluated_count" for documents it never looked at."""

    from app.agents.rag.vector import UnifiedVectorRAGAgent

    assert not hasattr(UnifiedVectorRAGAgent, "_evaluate_retrieval")
    assert not hasattr(UnifiedVectorRAGAgent(), "self_rag_evaluator")
