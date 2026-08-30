"""Thin LangGraph nodes that call typed services and enforce stage boundaries."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from app.domain.contracts import (
    EvidenceBundle,
    EvidenceItem,
    FinalAnswer,
    RouteDecision,
    TaskPlan,
    ToolResult,
    ValidationStatus,
)
from app.domain.errors import StageExecutionError
from app.domain.events import EventStage, ExecutionEvent
from app.domain.knowledge import AccessScope, EvidenceRef, KnowledgeStrategy
from app.domain.workflow import (
    CandidateAnswer,
    ClarificationResult,
    ContextBundle,
    RouterDecision,
    VerificationDecision,
)
from app.knowledge.context import ContextBuilder
from app.orchestration.langgraph.state import OrchestrationGraphState
from app.orchestration.policies import ExecutionPolicy
from app.orchestration.request import OrchestrationRequest, RequestScope
from app.orchestration.timeout_control import ExecutionBudget, run_with_timeout
from app.privacy.models import PrivacyResult
from app.privacy.service import PrivacyService
from app.services.security.access_scope import AccessScopeResolver

logger = logging.getLogger(__name__)


class WorkflowServices(Protocol):
    """Structural service bundle consumed by the graph nodes."""

    router: Callable[[OrchestrationRequest], Awaitable[RouteDecision]]
    planner: Callable[[OrchestrationRequest, RouteDecision], Awaitable[TaskPlan]]
    retriever: Callable[
        [OrchestrationRequest, RouteDecision, TaskPlan | None],
        Awaitable[EvidenceBundle],
    ]
    tool_runner: Callable[
        [OrchestrationRequest, RouteDecision, TaskPlan, EvidenceBundle],
        Awaitable[tuple[ToolResult, ...]],
    ]
    synthesizer: Callable[
        [OrchestrationRequest, RouteDecision, TaskPlan | None, EvidenceBundle, tuple[ToolResult, ...]],
        Awaitable[FinalAnswer],
    ]
    candidate_synthesizer: (
        Callable[
            [OrchestrationRequest, ContextBundle, tuple[ToolResult, ...]],
            Awaitable[CandidateAnswer],
        ]
        | None
    )
    finalizer: (
        Callable[
            [OrchestrationRequest, EvidenceBundle, FinalAnswer, ExecutionPolicy],
            Awaitable[FinalAnswer],
        ]
        | None
    )
    clarifier: Callable[[OrchestrationRequest, RouterDecision], Awaitable[ClarificationResult]] | None
    verifier: (
        Callable[
            [OrchestrationRequest, ContextBundle, CandidateAnswer, int],
            Awaitable[VerificationDecision],
        ]
        | None
    )
    knowledge_agent: Callable[
        [OrchestrationRequest, RouterDecision, TaskPlan | None, VerificationDecision | None],
        Awaitable[KnowledgeStrategy],
    ]
    knowledge_orchestrator: (
        Callable[
            [KnowledgeStrategy, Any, Callable[[ExecutionEvent], Awaitable[None]]],
            Awaitable[ContextBundle],
        ]
        | None
    )
    privacy: PrivacyService
    access_scope_resolver: AccessScopeResolver

    async def report_event(self, event: ExecutionEvent) -> None: ...


class WorkflowNodeRuntime:
    """Request-safe node implementation over immutable state updates."""

    def __init__(
        self,
        *,
        services: WorkflowServices,
        policy: ExecutionPolicy,
        max_verifier_retries: int,
        context_token_budget: int,
        monitor: Any = None,
    ) -> None:
        self._services = services
        self._policy = policy
        self._max_verifier_retries = max(0, min(1, int(max_verifier_retries)))
        self._context_builder = ContextBuilder(token_budget=context_token_budget)
        self._monitor = monitor

    async def privacy_permission(self, state: OrchestrationGraphState) -> dict[str, Any]:
        request = _required(state, "request", OrchestrationRequest)

        async def operation() -> tuple[PrivacyResult, Any, OrchestrationRequest]:
            privacy = self._services.privacy.inspect_input(request.question)
            if privacy.blocked:
                raise PermissionError("input privacy inspection blocked the request")
            scope = self._services.access_scope_resolver.resolve(request.actor, request.source_scope)
            sanitized = request.model_copy(
                update={"question": privacy.text, "source_scope": _scope_to_request_scope(scope, request)}
            )
            return privacy, scope, sanitized

        (privacy, scope, sanitized), event = await self._run_stage(
            state,
            event_stage="privacy_permission",
            timeout_stage="privacy_permission",
            operation=operation,
            expected_type=tuple,
        )
        return {
            "privacy": privacy,
            "permission_scope": scope,
            "request": sanitized,
            "complete_query": sanitized.question,
            "trace": (event,),
        }

    async def router(self, state: OrchestrationGraphState) -> dict[str, Any]:
        request = _required(state, "request", OrchestrationRequest)
        route, event = await self._run_stage(
            state,
            event_stage="route",
            timeout_stage="route",
            operation=lambda: self._services.router(request),
            expected_type=RouteDecision,
        )
        self._policy.validate_route(route)
        clarification_required = route.effective_route == "clarification"
        next_stage = (
            "clarification"
            if clarification_required
            else ("planner" if self._policy.should_plan(route) else "knowledge")
        )
        decision = RouterDecision(
            intent=route.intent,
            complexity="complex" if route.requires_plan else "simple",
            completeness="incomplete" if clarification_required else "complete",
            next_stage=next_stage,
            knowledge_hints=_knowledge_hints(route),
            confidence=route.confidence,
            reason=route.reason,
        )
        return {"route": route, "route_decision": decision, "trace": (event,)}

    async def clarification(self, state: OrchestrationGraphState) -> dict[str, Any]:
        request = _required(state, "request", OrchestrationRequest)
        route_decision = _required(state, "route_decision", RouterDecision)
        clarifier = self._services.clarifier
        if clarifier is None:
            raise StageExecutionError(
                "clarification",
                RuntimeError("clarification service is not configured"),
            )
        result, event = await self._run_stage(
            state,
            event_stage="clarification",
            timeout_stage="clarification",
            operation=lambda: clarifier(request, route_decision),
            expected_type=ClarificationResult,
        )
        if result.action == "ask":
            # Interactive clarification belongs to the HTTP clarification API
            # (POST /api/v1/clarification/check), which owns the multi-round
            # state.  Inside the pipeline nobody can answer the question, and the
            # clarifier is called without collected context so it always asks —
            # raising here turned every rag_design/comparison query into a 500.
            logger.info("clarification requested but not interactively resolvable; continuing with original query")
            complete_query = request.question
        else:
            complete_query = result.complete_query or request.question
        return {
            "clarification": result,
            "complete_query": complete_query,
            "request": request.model_copy(update={"question": complete_query}),
            "trace": (event,),
        }

    async def planner(self, state: OrchestrationGraphState) -> dict[str, Any]:
        request = _required(state, "request", OrchestrationRequest)
        route = _required(state, "route", RouteDecision)
        plan, event = await self._run_stage(
            state,
            event_stage="plan",
            timeout_stage="plan",
            operation=lambda: self._services.planner(request, route),
            expected_type=TaskPlan,
        )
        return {"task_plan": plan, "trace": (event,)}

    async def knowledge(self, state: OrchestrationGraphState) -> dict[str, Any]:
        request = _required(state, "request", OrchestrationRequest)
        route = _required(state, "route", RouteDecision)
        route_decision = _required(state, "route_decision", RouterDecision)
        plan = state.get("task_plan")
        retry_feedback = state.get("verification") if int(state.get("retry_count", 0)) > 0 else None
        strategy, strategy_event = await self._run_stage(
            state,
            event_stage="knowledge_strategy",
            timeout_stage="knowledge_strategy",
            operation=lambda: self._services.knowledge_agent(
                request,
                route_decision,
                plan,
                retry_feedback,
            ),
            expected_type=KnowledgeStrategy,
        )
        orchestrator = getattr(self._services, "knowledge_orchestrator", None)
        scope = state.get("permission_scope")
        if scope is None:
            raise StageExecutionError("knowledge", PermissionError("knowledge retrieval requires access scope"))
        if orchestrator is not None:
            context, event = await self._run_stage(
                state,
                event_stage="knowledge",
                timeout_stage="knowledge",
                operation=lambda: orchestrator(strategy, scope, self._services.report_event),
                expected_type=ContextBundle,
            )
            evidence = EvidenceBundle(
                route=route,
                plan=plan,
                items=context.evidence,
                diagnostics=context.diagnostics,
            )
        else:
            evidence, event = await self._run_stage(
                state,
                event_stage="knowledge",
                timeout_stage="knowledge",
                operation=lambda: self._services.retriever(request, route, plan),
                expected_type=EvidenceBundle,
            )
            context = self._context_builder.build(
                evidence.items,
                scope,
                diagnostics=dict(evidence.diagnostics),
            )
            evidence = evidence.model_copy(update={"items": context.evidence, "diagnostics": context.diagnostics})
        tool_results: tuple[ToolResult, ...] = ()
        trace = [strategy_event, event]
        if plan is not None and self._policy.should_run_tools(route, plan):
            tool_results, tool_event = await self._run_stage(
                state,
                event_stage="tool",
                timeout_stage="tool",
                operation=lambda: self._services.tool_runner(request, route, plan, evidence),
                expected_type=tuple,
                validator=_validate_tool_results,
            )
            trace.append(tool_event)
        return {
            "evidence_bundle": evidence,
            "knowledge_strategy": strategy,
            "context": context,
            "tool_results": tool_results,
            "trace": tuple(trace),
        }

    async def synthesizer(self, state: OrchestrationGraphState) -> dict[str, Any]:
        request = _required(state, "request", OrchestrationRequest)
        context = _required(state, "context", ContextBundle)
        tool_results = state.get("tool_results", ())
        candidate_synthesizer = getattr(self._services, "candidate_synthesizer", None)
        if candidate_synthesizer is not None:
            candidate_answer, event = await self._run_stage(
                state,
                event_stage="synthesize",
                timeout_stage="synthesize",
                operation=lambda: candidate_synthesizer(request, context, tool_results),
                expected_type=CandidateAnswer,
            )
            return {"candidate_answer": candidate_answer, "trace": (event,)}

        route = _required(state, "route", RouteDecision)
        evidence = _required(state, "evidence_bundle", EvidenceBundle)
        plan = state.get("task_plan")
        candidate, event = await self._run_stage(
            state,
            event_stage="synthesize",
            timeout_stage="synthesize",
            operation=lambda: self._services.synthesizer(request, route, plan, evidence, tool_results),
            expected_type=FinalAnswer,
        )
        references = tuple(
            EvidenceRef(
                document_id=item.document_id,
                version=item.version,
                page=item.page,
                chunk_id=item.chunk_id,
                image_id=item.image_id,
            )
            for item in evidence.items
            if item.version is not None
        )
        return {
            "candidate": candidate,
            "candidate_answer": CandidateAnswer(
                text=candidate.answer,
                citations=references,
                unresolved_items=candidate.unresolved_items,
            ),
            "trace": (event,),
        }

    async def verifier(self, state: OrchestrationGraphState) -> dict[str, Any]:
        request = _required(state, "request", OrchestrationRequest)
        evidence = _required(state, "evidence_bundle", EvidenceBundle)
        route = _required(state, "route", RouteDecision)
        context = _required(state, "context", ContextBundle)
        candidate_answer = _required(state, "candidate_answer", CandidateAnswer)
        verifier = self._services.verifier
        retry_count = int(state.get("retry_count", 0))
        if verifier is None:

            async def verification_operation() -> VerificationDecision:
                status = "degraded" if candidate_answer.unresolved_items else "approved"
                return VerificationDecision(status=status, missing_aspects=candidate_answer.unresolved_items)

        else:

            async def verification_operation() -> VerificationDecision:
                return await verifier(request, context, candidate_answer, retry_count)

        decision, verifier_event = await self._run_stage(
            state,
            event_stage="verifier",
            timeout_stage="verifier",
            operation=verification_operation,
            expected_type=VerificationDecision,
        )
        if decision.status == "retry_retrieval" and retry_count >= self._max_verifier_retries:
            decision = decision.model_copy(
                update={
                    "status": "degraded",
                    "retry_query": None,
                    "missing_aspects": tuple(decision.missing_aspects) + ("verifier retry budget exhausted",),
                }
            )
        if decision.status == "retry_retrieval":
            return {
                "verification": decision,
                "retry_count": retry_count + 1,
                "trace": (verifier_event,),
            }

        cited_items = _items_for_references(candidate_answer.citations, evidence)
        base_answer = FinalAnswer(
            answer=candidate_answer.text,
            citations=tuple(_citation_label(item.source, item.page) for item in cited_items),
            route=route,
            evidence=evidence,
            evidence_ids=tuple(item.item_id for item in cited_items),
            unresolved_items=candidate_answer.unresolved_items,
            conflict_notes=decision.conflicts,
            execution_summary=f"verifier={decision.status} evidence={len(evidence.items)}",
            validation=_verification_status(decision),
        )
        finalizer = self._services.finalizer
        trace = [verifier_event]
        if finalizer is None:
            answer = base_answer
        else:
            answer, finalize_event = await self._run_stage(
                state,
                event_stage="finalize",
                timeout_stage="finalize",
                operation=lambda: finalizer(request, evidence, base_answer, self._policy),
                expected_type=FinalAnswer,
            )
            trace.append(finalize_event)
        return {
            "final_answer": answer,
            "verification": decision,
            "retry_count": retry_count,
            "trace": tuple(trace),
        }

    async def output_filter(self, state: OrchestrationGraphState) -> dict[str, Any]:
        answer = _required(state, "final_answer", FinalAnswer)
        scope = state.get("permission_scope")
        evidence = _required(state, "evidence_bundle", EvidenceBundle)
        budget = _required(state, "budget", ExecutionBudget)

        async def operation() -> FinalAnswer:
            if scope is None:
                raise PermissionError("output filtering requires an access scope")
            cited_ids = frozenset(answer.evidence_ids)
            cited_items = tuple(item for item in evidence.items if item.item_id in cited_ids)
            dlp = self._services.privacy.filter_output(answer.answer, cited_items, scope)
            labels = tuple(_citation_label(item.source, item.page) for item in dlp.citations)
            safe_evidence = evidence.model_copy(update={"items": dlp.citations, "citations": labels})
            validation = answer.validation
            if dlp.dropped_citation_ids:
                validation = ValidationStatus(
                    state="degraded",
                    approved=False,
                    method=f"{answer.validation.method}+output_dlp",
                    issues=tuple(answer.validation.issues) + ("unauthorized citations removed",),
                )
            return answer.model_copy(
                update={
                    "answer": dlp.answer,
                    "citations": labels,
                    "evidence": safe_evidence,
                    "evidence_ids": tuple(item.item_id for item in dlp.citations),
                    "validation": validation,
                    "safety": {
                        **dict(answer.safety),
                        "output_dlp": {
                            "redactions": dlp.redaction_count,
                            "dropped_citations": len(dlp.dropped_citation_ids),
                        },
                    },
                    "execution_metadata": {
                        **dict(answer.execution_metadata),
                        "budget_stats": budget.get_stats(),
                        "orchestration_backend": "langgraph",
                    },
                }
            )

        filtered, event = await self._run_stage(
            state,
            event_stage="output_filter",
            timeout_stage="output_filter",
            operation=operation,
            expected_type=FinalAnswer,
        )
        return {"final_answer": filtered, "trace": (event,)}

    def after_router(self, state: OrchestrationGraphState) -> str:
        return _required(state, "route_decision", RouterDecision).next_stage

    def after_clarification(self, state: OrchestrationGraphState) -> str:
        decision = _required(state, "route_decision", RouterDecision)
        return "planner" if decision.complexity == "complex" else "knowledge"

    def after_verifier(self, state: OrchestrationGraphState) -> str:
        decision = _required(state, "verification", VerificationDecision)
        retry_count = int(state.get("retry_count", 0))
        if decision.status == "retry_retrieval" and 0 < retry_count <= self._max_verifier_retries:
            return "knowledge"
        return "output_filter"

    async def _run_stage(
        self,
        state: OrchestrationGraphState,
        *,
        event_stage: EventStage,
        timeout_stage: str,
        operation: Callable[[], Awaitable[Any]],
        expected_type: type[Any],
        validator: Callable[[Any], Any] | None = None,
    ) -> tuple[Any, ExecutionEvent]:
        budget = _required(state, "budget", ExecutionBudget)

        async def invoke() -> Any:
            return await run_with_timeout(timeout_stage, operation, budget)

        if self._monitor is not None:
            async with self._monitor.measure_async(f"orchestration_{event_stage}"):
                result = await invoke()
        else:
            result = await invoke()
        try:
            if validator is not None:
                result = validator(result)
            elif not isinstance(result, expected_type):
                raise TypeError(f"expected {expected_type.__name__}, got {type(result).__name__}")
        except Exception as exc:
            raise StageExecutionError(str(event_stage), exc) from exc
        event = ExecutionEvent(
            stage=event_stage,
            status="completed",
            duration_ms=int(budget.stage_times.get(timeout_stage, 0)),
        )
        await state["reporter"](event)
        return result, event


def _scope_to_request_scope(scope: AccessScope, request: OrchestrationRequest) -> RequestScope:
    """Narrow the request to exactly what the resolver authorized.

    Retrieval reads `request.source_scope`, not the resolved AccessScope, so a
    caller that passes no scope (RequestScope() -> None) or a wider one used to
    reach the store unfiltered. Rewriting it here means no downstream stage can
    be handed more than the resolver granted, whatever the caller sent.
    """

    return RequestScope(
        allowed_sources=scope.allowed_sources,
        document_ids=scope.document_ids,
        acl_tags=scope.acl_tags,
        allowed_fields=scope.allowed_fields,
        agent_class_hint=request.source_scope.agent_class_hint,
    )


def _required(state: OrchestrationGraphState, key: str, expected_type: type[Any]) -> Any:
    value = state.get(key)  # type: ignore[literal-required]
    if not isinstance(value, expected_type):
        raise StageExecutionError(key, TypeError(f"missing or invalid graph state value: {key}"))
    return value


def _validate_tool_results(value: Any) -> tuple[ToolResult, ...]:
    if not isinstance(value, tuple) or not all(isinstance(item, ToolResult) for item in value):
        raise TypeError("expected a tuple of ToolResult values")
    return value


def _items_for_references(
    references: tuple[EvidenceRef, ...],
    evidence: EvidenceBundle,
) -> tuple[EvidenceItem, ...]:
    """Resolve exact, versioned references without silently widening citations."""

    keys = {(ref.document_id, ref.version, ref.page, ref.chunk_id, ref.image_id) for ref in references}
    return tuple(
        item
        for item in evidence.items
        if (item.document_id, item.version, item.page, item.chunk_id, item.image_id) in keys
    )


def _verification_status(decision: VerificationDecision) -> ValidationStatus:
    issues = (
        tuple(decision.unsupported_claims)
        + tuple(decision.citation_errors)
        + tuple(decision.conflicts)
        + tuple(decision.missing_aspects)
    )
    if decision.status == "approved":
        return ValidationStatus(state="validated", approved=True, method="verifier", issues=issues)
    state = "rejected" if decision.status == "rejected" else "degraded"
    return ValidationStatus(state=state, approved=False, method="verifier", issues=issues)


def _knowledge_hints(route: RouteDecision) -> frozenset[str]:
    actual = route.effective_route
    if actual == "graph":
        return frozenset({"graph"})
    if actual == "web":
        return frozenset({"web"})
    if actual == "react":
        return frozenset({"tool"})
    if actual == "hybrid":
        return frozenset({"vector", "bm25"})
    return frozenset({"vector"})


def _citation_label(source: str, page: int | None) -> str:
    return f"{source}:{page}" if page is not None else source


__all__ = ["WorkflowNodeRuntime", "WorkflowServices"]
