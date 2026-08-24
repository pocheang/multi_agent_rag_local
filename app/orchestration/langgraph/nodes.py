"""Thin LangGraph nodes that call typed services and enforce stage boundaries."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from app.domain.contracts import (
    EvidenceBundle,
    FinalAnswer,
    RouteDecision,
    TaskPlan,
    ToolResult,
    ValidationStatus,
)
from app.domain.errors import StageExecutionError
from app.domain.events import EventStage, ExecutionEvent
from app.domain.knowledge import EvidenceRef
from app.domain.workflow import (
    CandidateAnswer,
    ClarificationResult,
    ContextBundle,
    RouterDecision,
    VerificationDecision,
)
from app.orchestration.langgraph.state import OrchestrationGraphState
from app.orchestration.policies import ExecutionPolicy
from app.orchestration.request import OrchestrationRequest
from app.orchestration.timeout_control import ExecutionBudget, run_with_timeout
from app.privacy.models import PrivacyResult
from app.privacy.service import PrivacyService
from app.services.security.access_scope import AccessScopeResolver


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
    finalizer: Callable[
        [OrchestrationRequest, EvidenceBundle, FinalAnswer, ExecutionPolicy],
        Awaitable[FinalAnswer],
    ] | None
    clarifier: Callable[[OrchestrationRequest, RouterDecision], Awaitable[ClarificationResult]] | None
    verifier: Callable[
        [OrchestrationRequest, ContextBundle, CandidateAnswer, int],
        Awaitable[VerificationDecision],
    ] | None
    privacy: PrivacyService
    access_scope_resolver: AccessScopeResolver


class WorkflowNodeRuntime:
    """Request-safe node implementation over immutable state updates."""

    def __init__(
        self,
        *,
        services: WorkflowServices,
        policy: ExecutionPolicy,
        max_verifier_retries: int,
        monitor: Any = None,
    ) -> None:
        self._services = services
        self._policy = policy
        self._max_verifier_retries = max(0, min(1, int(max_verifier_retries)))
        self._monitor = monitor

    async def privacy_permission(self, state: OrchestrationGraphState) -> dict[str, Any]:
        request = _required(state, "request", OrchestrationRequest)

        async def operation() -> tuple[PrivacyResult, Any, OrchestrationRequest]:
            privacy = self._services.privacy.inspect_input(request.question)
            if privacy.blocked:
                raise PermissionError("input privacy inspection blocked the request")
            scope = self._services.access_scope_resolver.resolve(request.actor, request.source_scope)
            sanitized = request.model_copy(update={"question": privacy.text})
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
        next_stage = "clarification" if clarification_required else (
            "planner" if self._policy.should_plan(route) else "knowledge"
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
            raise StageExecutionError(
                "clarification",
                RuntimeError(
                    "interactive clarification is required; use the clarification API with the returned thread"
                ),
            )
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
        plan = state.get("task_plan")
        evidence, event = await self._run_stage(
            state,
            event_stage="knowledge",
            timeout_stage="knowledge",
            operation=lambda: self._services.retriever(request, route, plan),
            expected_type=EvidenceBundle,
        )
        tool_results: tuple[ToolResult, ...] = ()
        trace = [event]
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
        context = ContextBundle(
            evidence=evidence.items,
            rendered_context="\n\n".join(item.content for item in evidence.items),
            diagnostics=dict(evidence.diagnostics),
        )
        return {
            "evidence_bundle": evidence,
            "context": context,
            "tool_results": tool_results,
            "trace": tuple(trace),
        }

    async def synthesizer(self, state: OrchestrationGraphState) -> dict[str, Any]:
        request = _required(state, "request", OrchestrationRequest)
        route = _required(state, "route", RouteDecision)
        evidence = _required(state, "evidence_bundle", EvidenceBundle)
        plan = state.get("task_plan")
        tool_results = state.get("tool_results", ())
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
        candidate = _required(state, "candidate", FinalAnswer)
        finalizer = self._services.finalizer
        if finalizer is None:

            async def operation() -> FinalAnswer:
                return candidate

        else:

            async def operation() -> FinalAnswer:
                return await finalizer(request, evidence, candidate, self._policy)

        verifier = self._services.verifier
        answer, event = await self._run_stage(
            state,
            event_stage="finalize" if verifier is not None else "verifier",
            timeout_stage="finalize",
            operation=operation,
            expected_type=FinalAnswer,
        )
        retry_count = int(state.get("retry_count", 0))
        trace = [event]
        if verifier is not None:
            context = _required(state, "context", ContextBundle)
            candidate_answer = _required(state, "candidate_answer", CandidateAnswer).model_copy(
                update={"text": answer.answer, "unresolved_items": answer.unresolved_items}
            )
            decision, verifier_event = await self._run_stage(
                state,
                event_stage="verifier",
                timeout_stage="verifier",
                operation=lambda: verifier(request, context, candidate_answer, retry_count),
                expected_type=VerificationDecision,
            )
            trace.append(verifier_event)
        else:
            status = "approved" if answer.validation.approved else answer.validation.state
            if status == "validated":
                status = "approved"
            decision = VerificationDecision(status=status)
        if decision.status == "retry_retrieval":
            retry_count += 1
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
            dlp = self._services.privacy.filter_output(answer.answer, evidence.items, scope)
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
        if decision.status == "retry_retrieval" and int(state.get("retry_count", 0)) <= self._max_verifier_retries:
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


def _required(state: OrchestrationGraphState, key: str, expected_type: type[Any]) -> Any:
    value = state.get(key)  # type: ignore[literal-required]
    if not isinstance(value, expected_type):
        raise StageExecutionError(key, TypeError(f"missing or invalid graph state value: {key}"))
    return value


def _validate_tool_results(value: Any) -> tuple[ToolResult, ...]:
    if not isinstance(value, tuple) or not all(isinstance(item, ToolResult) for item in value):
        raise TypeError("expected a tuple of ToolResult values")
    return value


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
