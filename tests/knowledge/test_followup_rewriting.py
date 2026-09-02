"""A follow-up question must not be retrieved on its pronoun.

`OrchestrationRequest.conversation` reached exactly two consumers -- the
synthesizer and the tool selector -- and neither of them retrieves. The router
saw only `request.question`, the Knowledge Agent used only `request.question` as
the retrieval query, and `build_rewrite_queries` took a query with no history.
So "它的成本呢？" ran a vector search on those five characters, and the
synthesizer then had to answer from evidence fetched for the wrong query. The
failure looked like poor retrieval rather than a missing resolution step.

The fix is the rewrite step the repository already had a slot for, given the one
argument it was missing. `app/services/context_management.py` implements the
older rule-based alternative (pronoun -> entity) and is deliberately *not* wired
here: it detects a follow-up by substring-matching a fixed pronoun list, and the
most common Chinese follow-up shape drops the subject entirely -- there is no
pronoun to match. It keeps its existing reader, the session export endpoint.
"""

from __future__ import annotations

import asyncio

import pytest

from app.domain.contracts import EvidenceItem
from app.domain.knowledge import AccessScope, KnowledgeSourcePlan, KnowledgeStrategy
from app.knowledge.adapters import CallableKnowledgeAdapter
from app.knowledge.orchestrator import KnowledgeOrchestrator, discard_trace
from app.pipeline.contracts import ConversationMessage
from app.services.security.access_scope import DEFAULT_CONTEXT_FIELDS

PRIOR_TURNS = (
    ConversationMessage(role="system", content="Short-term memory (latest rounds): ...rendered block..."),
    ConversationMessage(role="user", content="比亚迪的电池技术怎么样？"),
    ConversationMessage(role="assistant", content="比亚迪采用刀片电池，能量密度较高。"),
)
FOLLOW_UP = "成本呢？"
"""Zero anaphora: the subject is dropped entirely. No pronoun to resolve, which
is exactly the case rule-based coreference cannot see."""


def _scope() -> AccessScope:
    return AccessScope(
        tenant_id="alice",
        user_id="alice",
        role="viewer",
        allowed_sources=frozenset({"/uploads/alice/notes.pdf"}),
        allowed_fields=DEFAULT_CONTEXT_FIELDS,
    )


def _strategy(question: str) -> KnowledgeStrategy:
    return KnowledgeStrategy(
        sources=(KnowledgeSourcePlan(source="vector", queries=(question,), top_k=4, timeout_ms=5_000),),
        rewrite=True,
        rerank=False,
        rationale="test",
    )


def _run(rewriter, conversation=(), question: str = FOLLOW_UP):
    """Return the queries the vector adapter was actually asked to search."""
    searched: list[tuple[str, ...]] = []

    async def vector(plan, scope):
        searched.append(plan.queries)
        return (
            EvidenceItem(
                content="cost table",
                source="/uploads/alice/notes.pdf",
                document_id="doc-1",
                version=1,
                retriever="vector",
            ),
        )

    orchestrator = KnowledgeOrchestrator(
        adapters={"vector": CallableKnowledgeAdapter("vector", vector)},
        rewriter=rewriter,
    )
    bundle = asyncio.run(orchestrator.retrieve(_strategy(question), _scope(), discard_trace, conversation))
    return searched[0], bundle


class TestTheConversationReachesTheRewriter:
    def test_the_rewriter_is_handed_the_turns(self) -> None:
        seen: list[tuple] = []

        def rewriter(query: str, conversation) -> list[str]:
            seen.append((query, tuple(conversation)))
            return [query]

        _run(rewriter, PRIOR_TURNS)

        assert seen[0][0] == FOLLOW_UP
        assert seen[0][1] == PRIOR_TURNS

    def test_a_completed_question_is_what_gets_searched(self) -> None:
        queries, _ = _run(lambda q, c: ["比亚迪刀片电池的成本"], PRIOR_TURNS)

        assert "比亚迪刀片电池的成本" in queries

    def test_the_original_question_survives_the_rewrite(self) -> None:
        """A wrong completion must add a bad query, never replace the good one:
        the model is guessing what the user meant, and it can guess wrong."""
        queries, _ = _run(lambda q, c: ["完全跑偏的问题"], PRIOR_TURNS)

        assert queries[0] == FOLLOW_UP

    def test_the_turn_count_is_reported(self) -> None:
        _, bundle = _run(lambda q, c: [q], PRIOR_TURNS)

        assert bundle.diagnostics["rewrite_context_turns"] == len(PRIOR_TURNS)


class TestTheFlagGatesIt:
    def test_no_conversation_means_the_question_as_asked(self) -> None:
        seen: list[tuple] = []

        def rewriter(query: str, conversation) -> list[str]:
            seen.append(tuple(conversation))
            return [query]

        queries, _ = _run(rewriter, ())

        assert seen[0] == ()
        assert queries == (FOLLOW_UP,)

    def test_the_rag_service_drops_the_conversation_when_tracking_is_off(self) -> None:
        """The gate lives at the one place that decides what retrieval may know
        about the session, so it cannot be honoured on one path and forgotten on
        another."""
        import inspect

        from app.agents.rag.service import RAGAgentService

        source = inspect.getsource(RAGAgentService.retrieve)

        assert "request.conversation if request.enable_context_tracking else ()" in source

    def test_the_synthesizer_drops_it_too(self) -> None:
        import inspect

        from app.agents.synthesizer.service import SynthesizerAgentService

        source = inspect.getsource(SynthesizerAgentService.synthesize_candidate)

        assert "request.enable_context_tracking" in source


class TestThePrompt:
    """The rewriter's own contract, exercised against a stubbed model."""

    @staticmethod
    def _invoke(query: str, conversation) -> dict[str, str]:
        import app.services.query.rule_rewrite as rule_rewrite
        from app.services.runtime.request_context import request_context

        seen: dict[str, str] = {}

        class _Model:
            def invoke(self, messages):
                seen["system"] = messages[0][1]
                seen["human"] = messages[1][1]
                return type("R", (), {"content": "改写结果"})()

        original = rule_rewrite.get_chat_model
        rule_rewrite.get_chat_model = lambda *a, **k: _Model()
        try:
            with request_context(timeout_ms=5_000, overload_mode=False, api_settings=None):
                rule_rewrite._llm_rewrite(query, conversation)
        finally:
            rule_rewrite.get_chat_model = original
        return seen

    def test_history_switches_to_the_standalone_prompt(self) -> None:
        with_history = self._invoke(FOLLOW_UP, PRIOR_TURNS)
        first_turn = self._invoke("什么是刀片电池", ())

        assert "standalone" in with_history["system"]
        assert "standalone" not in first_turn["system"]

    def test_the_rendered_memory_block_is_not_fed_back(self) -> None:
        """A `system` turn on this path holds an already-rendered summary of the
        same rounds; including it would show the model one thing twice."""
        seen = self._invoke(FOLLOW_UP, PRIOR_TURNS)

        assert "rendered block" not in seen["human"]
        assert "比亚迪的电池技术怎么样？" in seen["human"]

    def test_turns_are_ordered_oldest_first(self) -> None:
        human = self._invoke(FOLLOW_UP, PRIOR_TURNS)["human"]

        assert human.index("比亚迪的电池技术怎么样？") < human.index("刀片电池，能量密度")

    def test_no_deadline_still_declines(self) -> None:
        """`request_context` is what makes the rewriter runnable at all; outside
        one it must not spend an LLM call it has no budget for."""
        import app.services.query.rule_rewrite as rule_rewrite

        assert rule_rewrite._llm_rewrite(FOLLOW_UP, PRIOR_TURNS) is None


class TestWhyNotTheRuleBasedResolver:
    """Why `app/services/context_management.py` is not what gets wired here.

    It decides a question needs resolving by substring-matching a fixed pronoun
    list. Both directions fail on ordinary Chinese, and they fail differently.
    Pinned so that reviving it stays a deliberate choice made with this in view.
    """

    @staticmethod
    def _resolver():
        from app.services.context_management import CoreferenceResolver

        return CoreferenceResolver()

    @pytest.mark.parametrize("question", ["成本呢？", "对比一下", "多少钱"])
    def test_a_dropped_subject_is_invisible_to_it(self, question: str) -> None:
        """The most common Chinese follow-up shape carries no pronoun at all, so
        there is nothing to match and the question passes through unresolved."""
        assert self._resolver()._has_coreference(question) is False

    @pytest.mark.parametrize("question", ["那延迟呢", "这样做的成本是多少"])
    def test_a_discourse_particle_reads_as_a_pronoun(self, question: str) -> None:
        """The opposite failure: 那/这 are substrings of ordinary words and
        particles, so a self-contained question is judged to need resolving and
        gets a stale entity substituted into it."""
        assert self._resolver()._has_coreference(question) is True
