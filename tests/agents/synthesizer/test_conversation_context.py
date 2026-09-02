"""Regression test: conversation turns must reach the generator.

``OrchestrationRequest.conversation`` was populated by the pipeline boundary but
read by nothing, so multi-turn context was silently dropped before generation.
``synthesize_answer`` has always accepted ``memory_context``; the synthesizer
just never passed it.
"""

from __future__ import annotations

import pytest

from app.agents.synthesizer.service import SynthesizerAgentService, _render_conversation
from app.domain.contracts import EvidenceItem
from app.domain.workflow import ContextBundle
from app.orchestration.request import ConversationTurn, OrchestrationRequest


def _context() -> ContextBundle:
    return ContextBundle(
        evidence=(EvidenceItem(content="Doc B covers Y.", source="docB", document_id="docB", page=1),),
        rendered_context="[E1] document=docB, page=1; Doc B covers Y.",
    )


def test_render_conversation_includes_both_roles():
    rendered = _render_conversation(
        (
            ConversationTurn(role="user", content="Tell me about doc A."),
            ConversationTurn(role="assistant", content="Doc A covers X."),
        )
    )
    assert "Tell me about doc A." in rendered
    assert "Doc A covers X." in rendered


def test_render_conversation_is_empty_for_no_turns():
    assert _render_conversation(()) == ""


def test_render_conversation_skips_blank_turns():
    assert _render_conversation((ConversationTurn(role="user", content="   "),)) == ""


def test_render_conversation_is_bounded_on_both_axes():
    turns = tuple(ConversationTurn(role="user", content="x" * 500) for _ in range(40))
    rendered = _render_conversation(turns)
    assert len(rendered) <= 4000
    # Only the most recent turns survive the turn cap.
    assert rendered.count("user:") <= 12


@pytest.mark.asyncio
async def test_conversation_is_passed_as_memory_context():
    captured: dict = {}

    def fake_generate(question, skill_name, **kwargs):
        captured.update(kwargs)
        return {"answer": "ok [E1]"}

    service = SynthesizerAgentService(generate=fake_generate)
    request = OrchestrationRequest(
        question="And what about the second one?",
        conversation=(
            ConversationTurn(role="user", content="Tell me about doc A."),
            ConversationTurn(role="assistant", content="Doc A covers X."),
        ),
    )

    await service.synthesize_candidate(request, _context(), ())

    assert "Doc A covers X." in captured["memory_context"]
    assert "Tell me about doc A." in captured["memory_context"]


@pytest.mark.asyncio
async def test_empty_conversation_keeps_memory_context_empty():
    captured: dict = {}

    def fake_generate(question, skill_name, **kwargs):
        captured.update(kwargs)
        return {"answer": "ok [E1]"}

    service = SynthesizerAgentService(generate=fake_generate)
    request = OrchestrationRequest(question="Standalone question.")

    await service.synthesize_candidate(request, _context(), ())

    assert captured["memory_context"] == ""
