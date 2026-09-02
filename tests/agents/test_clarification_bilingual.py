"""Regression tests for clarification language and non-fatal degradation.

Two defects: the question catalogue was Chinese-only in a system that promises
bilingual support, and the in-pipeline clarification node raised on
``action == "ask"`` — which it always returns there, because the pipeline calls
the clarifier without any collected context.
"""

from __future__ import annotations

import inspect

from app.agents.clarification.rules import question_for
from app.orchestration.langgraph import nodes


def _has_cjk(text: str) -> bool:
    return any("一" <= ch <= "鿿" for ch in text)


def test_chinese_question_is_the_default():
    q = question_for("rag_design", "scenario")
    assert q is not None
    assert _has_cjk(q.question)


def test_english_question_is_available():
    q = question_for("rag_design", "scenario", language="en")
    assert q is not None
    assert not _has_cjk(q.question)
    assert q.field_name == "scenario"
    assert q.options


def test_both_languages_agree_on_field_names_and_option_counts():
    catalogue = {
        "rag_design": ("scenario", "data_source", "scale", "performance_requirement"),
        "document_comparison": ("doc_ids", "comparison_aspect", "output_format"),
    }
    for intent, fields in catalogue.items():
        for field_name in fields:
            zh = question_for(intent, field_name)
            en = question_for(intent, field_name, language="en")
            assert zh is not None and en is not None, f"{intent}.{field_name}"
            assert zh.field_name == en.field_name
            assert len(zh.options) == len(en.options)
            assert zh.allow_custom_input == en.allow_custom_input


def test_unknown_language_falls_back_to_chinese():
    q = question_for("rag_design", "scenario", language="fr")
    assert q is not None
    assert _has_cjk(q.question)


def test_unknown_field_still_returns_none():
    assert question_for("rag_design", "nope") is None
    assert question_for("nope", "scenario", language="en") is None


def test_clarification_node_does_not_raise_on_ask():
    """Interactive clarification is owned by the HTTP API; inside the pipeline
    nobody can answer, so the node must continue with the original query."""
    source = inspect.getsource(nodes.WorkflowNodeRuntime.clarification)
    ask_branch = source.split('if result.action == "ask":', 1)[1].split("complete_query", 1)[0]
    assert "raise" not in ask_branch, "the ask branch must degrade, not raise"
