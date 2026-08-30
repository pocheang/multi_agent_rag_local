"""The resolved AccessScope must constrain retrieval, not just the output.

`privacy_permission` resolves the caller's identity into an AccessScope and puts
it in graph state under `permission_scope`. Retrieval, however, reads
`request.source_scope` -- whatever the caller handed in. The two agree today only
because the API layer computes the same visible-source list twice
(app/api/routes/public/query.py:67). Callers that do not, do not:
`app/api/routes/internal/pipeline_contract.py:63` forwards `allowed_sources=None`
and `app/api/routes/public/clarification.py:147` builds an empty RequestScope,
and both mean "search everything" once they reach the store.

The fix is for `privacy_permission` to rewrite `request.source_scope` from the
scope it just resolved, so retrieval cannot be handed a wider range than the
resolver authorized. See P0-1 step 4 in
docs/superpowers/plans/2026-08-29-user-data-isolation.md.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.domain.events import ExecutionEvent
from app.orchestration.langgraph.nodes import WorkflowNodeRuntime
from app.orchestration.policies import ExecutionPolicy
from app.orchestration.request import OrchestrationRequest, RequestActor, RequestScope
from app.orchestration.timeout_control import ExecutionBudget, TimeoutConfig
from app.pipeline.profiles import PipelineProfile
from app.privacy.service import PrivacyService
from app.services.security.access_scope import AccessScopeError, AccessScopeResolver

ALICE_DOC = "/uploads/alice/notes.pdf"
BOB_DOC = "/uploads/bob/salary.pdf"

_ROWS = [
    {"source": ALICE_DOC, "document_id": "doc-alice", "owner_user_id": "alice", "visibility": "private"},
    {"source": BOB_DOC, "document_id": "doc-bob", "owner_user_id": "bob", "visibility": "private"},
]


class _Services:
    """Only the two attributes privacy_permission touches."""

    def __init__(self) -> None:
        self.privacy = PrivacyService()
        self.access_scope_resolver = AccessScopeResolver(
            document_provider=lambda actor: [row for row in _ROWS if row["owner_user_id"] == actor.get("user_id")]
        )

    async def report_event(self, event: ExecutionEvent) -> None:
        del event


def _runtime() -> WorkflowNodeRuntime:
    return WorkflowNodeRuntime(
        services=_Services(),
        policy=ExecutionPolicy.for_profile(PipelineProfile.ADVANCED),
        max_verifier_retries=1,
        context_token_budget=4000,
    )


def _state(request: OrchestrationRequest) -> dict[str, Any]:
    async def reporter(event: ExecutionEvent) -> None:
        del event

    return {
        "request": request,
        "budget": ExecutionBudget(TimeoutConfig()),
        "reporter": reporter,
    }


def _alice(scope: RequestScope) -> OrchestrationRequest:
    return OrchestrationRequest(
        question="what did the review say",
        actor=RequestActor(user_id="alice", tenant_id="alice", role="viewer"),
        source_scope=scope,
    )


# --- what already holds ----------------------------------------------------


@pytest.mark.asyncio
async def test_resolver_rejects_a_caller_asking_for_someone_elses_source():
    """A caller cannot widen its own scope by naming another user's document."""
    request = _alice(RequestScope(allowed_sources=frozenset({BOB_DOC})))

    with pytest.raises(Exception) as excinfo:
        await _runtime().privacy_permission(_state(request))

    assert isinstance(excinfo.value.__cause__ or excinfo.value, AccessScopeError | PermissionError)


@pytest.mark.asyncio
async def test_resolved_scope_is_published_to_graph_state():
    result = await _runtime().privacy_permission(_state(_alice(RequestScope())))

    assert result["permission_scope"].allowed_sources == frozenset({ALICE_DOC})
    assert result["permission_scope"].user_id == "alice"


# --- P0-1 step 4: fixed 2026-08-30 -----------------------------------------


@pytest.mark.asyncio
async def test_an_absent_caller_scope_is_replaced_by_the_resolved_one():
    """RequestScope() means 'unrestricted' downstream; it must not survive.

    This is the single change that makes every other caller safe: after this
    node, retrieval physically cannot be handed a wider range than the resolver
    authorized, regardless of what the API layer passed in.
    """
    result = await _runtime().privacy_permission(_state(_alice(RequestScope())))

    assert result["request"].source_scope.allowed_sources == frozenset({ALICE_DOC})


@pytest.mark.asyncio
async def test_the_rewritten_scope_carries_every_resolved_dimension():
    result = await _runtime().privacy_permission(_state(_alice(RequestScope())))
    scope = result["permission_scope"]
    rewritten = result["request"].source_scope

    assert rewritten.document_ids == scope.document_ids
    assert rewritten.acl_tags == scope.acl_tags
    assert rewritten.allowed_fields == scope.allowed_fields


@pytest.mark.asyncio
async def test_the_sanitized_question_still_survives_the_rewrite():
    """Guards the rewrite against clobbering what the node already does."""
    result = await _runtime().privacy_permission(_state(_alice(RequestScope())))

    assert result["request"].question
    assert result["complete_query"] == result["request"].question


# --- the same property, proven through the real graph ----------------------


class _RecordingCapabilities:
    """Real graph, stubbed stages, so the retriever can report what it received."""

    typed_tools = None

    def __init__(self) -> None:
        self.seen: list[OrchestrationRequest] = []

    def orchestration_services(self):
        from app.domain.contracts import EvidenceBundle, FinalAnswer, RouteDecision, TaskPlan, ValidationStatus
        from app.orchestration.engine import OrchestrationServices

        route = RouteDecision(
            intent="knowledge_retrieval",
            route="vector",
            confidence=0.9,
            requires_plan=False,
            reason="stub",
        )

        async def router(request):
            return route

        async def planner(request, decision):
            return TaskPlan()

        async def retriever(request, decision, plan):
            self.seen.append(request)
            return EvidenceBundle(route=decision, plan=plan)

        async def tool_runner(request, decision, plan, evidence):
            return ()

        async def synthesizer(request, decision, plan, evidence, tool_results):
            return FinalAnswer(
                answer="stubbed answer",
                route=decision,
                evidence=evidence,
                validation=ValidationStatus(state="validated", approved=True, method="stub"),
            )

        return OrchestrationServices(
            router=router,
            planner=planner,
            retriever=retriever,
            tool_runner=tool_runner,
            synthesizer=synthesizer,
            access_scope_resolver=_Services().access_scope_resolver,
        )


@pytest.mark.asyncio
async def test_the_graph_hands_retrieval_the_resolved_scope(monkeypatch):
    """End-to-end: a caller that supplies no scope still cannot search everything.

    This is the property that makes `pipeline_contract.py`'s `allowed_sources=None`
    and `clarification.py`'s empty RequestScope safe without touching either.
    """
    from app.pipeline.contracts import PipelineRequest, PipelineUser
    from app.pipeline.profiles import PipelineProfile
    from app.pipeline.rag_pipeline import RAGPipeline

    capabilities = _RecordingCapabilities()
    await RAGPipeline(capabilities=capabilities).execute(
        PipelineRequest(
            question="what did the review say",
            profile=PipelineProfile.ADVANCED,
            user=PipelineUser(user_id="alice", tenant_id="alice", username="alice", role="viewer"),
        )
    )

    assert capabilities.seen, "the retriever stage never ran"
    assert capabilities.seen[0].source_scope.allowed_sources == frozenset({ALICE_DOC})
