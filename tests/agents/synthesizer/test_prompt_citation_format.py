"""Regression test: every citation-instructing prompt must describe the
[E1]/[E2] evidence-marker convention the system actually renders and
allow-lists, not the unused [doc_id:page] format."""

from __future__ import annotations

import pytest

from app.agents.synthesizer.templates import (
    COMPARISON_TEMPLATE,
    CONCEPT_TEMPLATE,
    COT_REASONING_PROMPT,
    GENERAL_TEMPLATE,
    PROCEDURAL_TEMPLATE,
    RELATIONSHIP_TEMPLATE,
)
from app.prompts.core.canonical_agent_prompts import ANSWER_PROMPT, REVIEW_PROMPT

_STALE_MARKERS = ("doc_id:page", "doc1:p3", "doc1:p5", "doc2:p1")


@pytest.mark.parametrize(
    "prompt_text",
    [
        ANSWER_PROMPT,
        REVIEW_PROMPT,
        CONCEPT_TEMPLATE,
        COMPARISON_TEMPLATE,
        RELATIONSHIP_TEMPLATE,
        PROCEDURAL_TEMPLATE,
        GENERAL_TEMPLATE,
        COT_REASONING_PROMPT,
    ],
)
def test_prompt_does_not_teach_the_unused_doc_id_page_format(prompt_text: str):
    for stale_marker in _STALE_MARKERS:
        assert stale_marker not in prompt_text, f"found stale marker {stale_marker!r}"


def test_answer_prompt_teaches_the_evidence_marker_format():
    assert "[E1]" in ANSWER_PROMPT
