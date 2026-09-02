"""With no documents to search, search the web instead of refusing.

An account that has uploaded nothing had exactly one possible outcome for every
question: the document sources were skipped (correctly -- there is nothing
there), no other source was selected, and synthesis returned the "no evidence"
message. That is the state every new account starts in, and the web search that
could have answered was already configured, keyless, and working.

Three things kept it out of reach, and fixing any one alone was not enough:

1. `use_web_fallback` had no way to become true on the chat path -- the HTTP
   request had no field for it and `query.py` never passed one, so its default
   of False was the only value the chat path ever saw.
2. Even set, it additionally required freshness keywords in the question, which
   "what are the security risks of RAG systems?" does not have.
3. `KnowledgeAgentService.decide` took no scope, so it could not know that local
   retrieval had nothing to search -- although the graph node read that scope
   twelve lines below, for the retrieval call.

The third is the one that matters here. The other two authorizations ask whether
this *question* would benefit from the web; this one observes that local
retrieval cannot answer at all.
"""

from __future__ import annotations

import asyncio

import pytest

from app.agents.knowledge.service import KnowledgeAgentService
from app.core.config import Settings
from app.domain.knowledge import AccessScope, KnowledgeSourcePlan, KnowledgeStrategy
from app.domain.workflow import RouterDecision
from app.orchestration.request import OrchestrationRequest
from app.services.security.access_scope import DEFAULT_CONTEXT_FIELDS

NO_FRESHNESS_WORDS = "what are the security risks of rag systems?"


def _scope(*sources: str) -> AccessScope:
    return AccessScope(
        tenant_id="alice",
        user_id="alice",
        role="viewer",
        allowed_sources=frozenset(sources),
        allowed_fields=DEFAULT_CONTEXT_FIELDS,
    )


def _route(*hints: str) -> RouterDecision:
    return RouterDecision(
        intent="knowledge_retrieval",
        complexity="simple",
        completeness="complete",
        next_stage="knowledge",
        confidence=0.7,
        reason="test",
        knowledge_hints=frozenset(hints or ("vector", "bm25")),
    )


def _sources(question: str, scope: AccessScope | None, **request_kwargs) -> tuple[str, ...]:
    service = KnowledgeAgentService()
    request = OrchestrationRequest(question=question, **request_kwargs)
    strategy = asyncio.run(service.decide(request, _route(), None, None, scope))
    return tuple(plan.source for plan in strategy.sources)


class TestAnEmptyCorpusReachesTheWeb:
    def test_a_user_with_no_documents_gets_web_search(self) -> None:
        assert "web" in _sources(NO_FRESHNESS_WORDS, _scope())

    def test_it_does_not_need_freshness_wording(self) -> None:
        """The existing keyword rule asks whether the question wants fresh
        information. This authorization is about the corpus, not the question."""
        assert "web" in _sources("explain retrieval augmented generation", _scope())

    def test_it_does_not_need_use_web_fallback(self) -> None:
        assert "web" in _sources(NO_FRESHNESS_WORDS, _scope(), use_web_fallback=False)

    def test_the_document_sources_are_still_selected(self) -> None:
        """Selection does not skip them -- the orchestrator does, and it records
        why. Dropping them here would hide that from the trace."""
        assert {"vector", "bm25"} <= set(_sources(NO_FRESHNESS_WORDS, _scope()))

    def test_the_reason_says_why(self) -> None:
        service = KnowledgeAgentService()
        strategy = asyncio.run(
            service.decide(OrchestrationRequest(question=NO_FRESHNESS_WORDS), _route(), None, None, _scope())
        )

        assert "empty document corpus" in strategy.rationale


class TestItStaysBounded:
    def test_a_user_with_documents_does_not_get_web(self) -> None:
        """Local retrieval can answer, so this authorization does not apply.
        Widening it to everyone would send every question to a third party."""
        assert "web" not in _sources(NO_FRESHNESS_WORDS, _scope("/uploads/alice/notes.pdf"))

    def test_an_absent_scope_is_not_an_empty_one(self) -> None:
        """`None` means the caller did not say. Reading it as "no documents"
        would reach the web on every request that happens to omit a scope."""
        assert "web" not in _sources(NO_FRESHNESS_WORDS, None)

    def test_the_setting_turns_it_off(self) -> None:
        """It sends the question to a third party, so a deployment that must not
        reach the internet has to be able to say so."""
        service = KnowledgeAgentService(settings=Settings(WEB_SEARCH_ON_EMPTY_CORPUS=False))
        strategy = asyncio.run(
            service.decide(OrchestrationRequest(question=NO_FRESHNESS_WORDS), _route(), None, None, _scope())
        )

        assert "web" not in tuple(plan.source for plan in strategy.sources)

    def test_a_deciders_web_plan_is_authorized_the_same_way(self) -> None:
        """`_bounded` guards a decider's output; before this it accepted web only
        with `use_web_fallback`, which would have dropped it right back out."""

        async def decider(request, route, plan, retry_feedback):
            return KnowledgeStrategy(
                sources=(KnowledgeSourcePlan(source="web", queries=("q",), top_k=4, timeout_ms=5_000),),
                rationale="decider",
            )

        service = KnowledgeAgentService(decider=decider)
        strategy = asyncio.run(
            service.decide(OrchestrationRequest(question=NO_FRESHNESS_WORDS), _route(), None, None, _scope())
        )

        assert tuple(plan.source for plan in strategy.sources) == ("web",)


def test_the_graph_node_hands_the_scope_to_source_selection() -> None:
    """The scope was already in the node's state and read for the retrieval call
    twelve lines below; withholding it from the decision about *what* to retrieve
    is what made the empty-corpus case undecidable."""
    import inspect

    from app.orchestration.langgraph.nodes import WorkflowNodeRuntime

    source = inspect.getsource(WorkflowNodeRuntime.knowledge)

    assert 'strategy_scope = state.get("permission_scope")' in source
    assert "strategy_scope," in source


@pytest.mark.parametrize("field", ["use_web_fallback"])
def test_the_http_request_exposes_the_control(field: str) -> None:
    """Reason 1: the flag existed on the contract with no way for a caller to
    set it, so its default was the only value the chat path ever saw."""
    from app.api.routes.public.query import AdvancedRAGRequest

    assert field in AdvancedRAGRequest.model_fields
