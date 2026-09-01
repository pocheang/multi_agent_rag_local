"""The output filter owns the answer a user actually reads.

It is the first stage that knows which citations survive DLP, so it is where
internal `[E{k}]` markers become `[1]`, `[2]` and the reference list is
appended. Before this, `[E1]` reached the browser verbatim with nothing to
resolve it against: the marker rewrite lived only in
`SynthesizerAgentService.synthesize()`, which the LangGraph path never calls.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.domain.contracts import EvidenceBundle, EvidenceItem, FinalAnswer
from app.domain.knowledge import AccessScope
from app.orchestration.langgraph.nodes import WorkflowNodeRuntime
from app.orchestration.policies import ExecutionPolicy
from app.orchestration.request import OrchestrationRequest
from app.orchestration.timeout_control import ExecutionBudget, TimeoutConfig
from app.privacy.service import PrivacyService
from app.services.security.access_scope import DEFAULT_CONTEXT_FIELDS


def _runtime() -> WorkflowNodeRuntime:
    return WorkflowNodeRuntime(
        services=SimpleNamespace(privacy=PrivacyService()),
        policy=ExecutionPolicy(),
        max_verifier_retries=1,
        context_token_budget=2000,
    )


def _local(source: str, page: int, content: str = "excerpt text") -> EvidenceItem:
    return EvidenceItem(
        content=content,
        source=source,
        document_id=source,
        version=1,
        page=page,
        retriever="vector",
    )


def _scope(*sources: str) -> AccessScope:
    return AccessScope(
        tenant_id="tenant-1",
        user_id="user-1",
        role="viewer",
        allowed_sources=frozenset(sources),
        allowed_fields=DEFAULT_CONTEXT_FIELDS,
    )


async def _run(runtime: WorkflowNodeRuntime, *, answer_text: str, items, scope, question: str) -> FinalAnswer:
    evidence = EvidenceBundle(items=tuple(items))
    state = {
        "request": OrchestrationRequest(question=question),
        "final_answer": FinalAnswer(
            answer=answer_text,
            evidence=evidence,
            evidence_ids=tuple(item.item_id for item in items),
        ),
        "evidence_bundle": evidence,
        "permission_scope": scope,
        "budget": ExecutionBudget(TimeoutConfig()),
        "reporter": _discard,
    }
    result = await runtime.output_filter(state)
    return result["final_answer"]


async def _discard(_event: object) -> None:
    return None


@pytest.mark.asyncio
async def test_internal_markers_become_numbered_citations_with_a_reference_list():
    first, second = _local("a.pdf", 1), _local("b.pdf", 2)

    answer = await _run(
        _runtime(),
        answer_text="第一点 [E1]。第二点 [E2]。",
        items=(first, second),
        scope=_scope("a.pdf", "b.pdf"),
        question="有哪些要点？",
    )

    assert "[E1]" not in answer.answer
    assert "第一点 [1]。第二点 [2]。" in answer.answer
    assert answer.answer.endswith("**参考来源**\n\n- [1] a.pdf · 第 1 页\n- [2] b.pdf · 第 2 页")


@pytest.mark.asyncio
async def test_the_reference_list_language_follows_the_answer():
    answer = await _run(
        _runtime(),
        answer_text="The first point [E1].",
        items=(_local("a.pdf", 1),),
        scope=_scope("a.pdf"),
        question="What are the points?",
    )

    assert "**References**" in answer.answer
    assert "- [1] a.pdf · p. 1" in answer.answer


@pytest.mark.asyncio
async def test_cited_evidence_comes_back_in_citation_order_so_entry_n_matches_marker_n():
    first, second = _local("a.pdf", 1), _local("b.pdf", 2)

    answer = await _run(
        _runtime(),
        answer_text="Second first [E2]. Then the other [E1].",
        items=(first, second),
        scope=_scope("a.pdf", "b.pdf"),
        question="Which order?",
    )

    assert [item.source for item in answer.cited_evidence] == ["b.pdf", "a.pdf"]
    assert answer.evidence_ids == (second.item_id, first.item_id)
    assert answer.citations == ("b.pdf:2", "a.pdf:1")


@pytest.mark.asyncio
async def test_uncited_evidence_still_comes_back_as_retrieved_context():
    """`evidence` and `cited_evidence` answer different questions: what the
    answer had available, and what it used. Collapsing them hid every retrieved
    chunk the model chose not to cite."""
    cited, uncited = _local("a.pdf", 1), _local("b.pdf", 2)

    answer = await _run(
        _runtime(),
        answer_text="Only the first one matters [E1].",
        items=(cited, uncited),
        scope=_scope("a.pdf", "b.pdf"),
        question="Which matters?",
    )

    assert [item.source for item in answer.cited_evidence] == ["a.pdf"]
    assert [item.source for item in answer.evidence.items] == ["a.pdf", "b.pdf"]


@pytest.mark.asyncio
async def test_a_citation_the_filter_drops_leaves_no_dangling_number():
    kept, unauthorized = _local("a.pdf", 1), _local("someone-else.pdf", 4)

    answer = await _run(
        _runtime(),
        answer_text="Allowed [E1]. Not allowed [E2].",
        items=(kept, unauthorized),
        scope=_scope("a.pdf"),
        question="Which sources?",
    )

    assert "[2]" not in answer.answer
    assert "Allowed [1]. Not allowed." in answer.answer
    assert [item.source for item in answer.evidence.items] == ["a.pdf"]
    assert answer.validation.state == "degraded"


@pytest.mark.asyncio
async def test_unversioned_web_evidence_reaches_the_reference_list():
    web = EvidenceItem(
        content="A web excerpt.",
        source="https://example.com/rag",
        document_id="https://example.com/rag",
        version=None,
        layer="web",
        retriever="web",
    )

    answer = await _run(
        _runtime(),
        answer_text="According to the web [E1].",
        items=(web,),
        scope=_scope("a.pdf"),
        question="What does the web say?",
    )

    assert "According to the web [1]." in answer.answer
    assert "- [1] https://example.com/rag" in answer.answer


@pytest.mark.asyncio
async def test_an_answer_with_no_citations_gets_no_empty_reference_heading():
    answer = await _run(
        _runtime(),
        answer_text="No evidence supported this.",
        items=(),
        scope=_scope("a.pdf"),
        question="Anything?",
    )

    assert answer.answer == "No evidence supported this."
    assert "参考来源" not in answer.answer
    assert "References" not in answer.answer
