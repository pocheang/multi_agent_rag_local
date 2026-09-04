"""Thin LangGraph nodes that call typed services and enforce stage boundaries."""

from __future__ import annotations

import logging
import re
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from app.agents.shared.config import SKILL_DEFAULT
from app.agents.synthesizer.citations import number_evidence_markers, render_reference_list
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
from app.domain.events import EventMetadata, EventStage, ExecutionEvent
from app.domain.knowledge import AccessScope, EvidenceRef, KnowledgeSourcePlan, KnowledgeStrategy
from app.domain.workflow import (
    CandidateAnswer,
    ContextBundle,
    RouterDecision,
    VerificationDecision,
)
from app.knowledge.context import ContextBuilder
from app.orchestration.langgraph.state import OrchestrationGraphState
from app.orchestration.policies import ExecutionPolicy
from app.orchestration.request import OrchestrationRequest, RequestScope
from app.orchestration.timeout_control import ExecutionBudget, StageTimeoutError, run_with_timeout
from app.privacy.models import PrivacyResult
from app.privacy.service import PrivacyService
from app.services.security.access_scope import AccessScopeResolver

logger = logging.getLogger(__name__)


class WorkflowServices(Protocol):
    """Structural service bundle consumed by the graph nodes."""

    router: Callable[[OrchestrationRequest], Awaitable[RouteDecision]]
    planner: Callable[[OrchestrationRequest, RouteDecision], Awaitable[TaskPlan]]
    retriever: Callable[
        [OrchestrationRequest, RouteDecision, TaskPlan | None, KnowledgeStrategy, AccessScope],
        Awaitable[ContextBundle],
    ]
    # No EvidenceBundle: the tool path must not be reachable from retrieved
    # content. See app/agents/tool/selector.py for the threat model.
    tool_runner: Callable[
        [OrchestrationRequest, RouteDecision, TaskPlan],
        Awaitable[tuple[ToolResult, ...]],
    ]
    synthesizer: Callable[
        [OrchestrationRequest, RouteDecision, TaskPlan | None, EvidenceBundle, tuple[ToolResult, ...]],
        Awaitable[FinalAnswer],
    ]
    # The trailing `str` is the router's chosen skill, which decides the shape
    # of the answer. See app/agents/synthesizer/skills.py.
    candidate_synthesizer: (
        Callable[
            [OrchestrationRequest, ContextBundle, tuple[ToolResult, ...], str],
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
    verifier: (
        Callable[
            [OrchestrationRequest, ContextBundle, CandidateAnswer, int],
            Awaitable[VerificationDecision],
        ]
        | None
    )
    knowledge_agent: Callable[
        [
            OrchestrationRequest,
            RouterDecision,
            TaskPlan | None,
            VerificationDecision | None,
            AccessScope | None,
        ],
        Awaitable[KnowledgeStrategy],
    ]
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

        # No on_timeout: this stage resolves the caller's access scope, and
        # everything downstream reads the scope it produces. Continuing without
        # one would search unscoped, so a timeout here must fail the request.
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
            # The same safe route the legacy router already picks when its own
            # LLM call fails: local vector retrieval, no plan, no tools.
            on_timeout=_timed_out_route,
        )
        self._policy.validate_route(route)
        # Still reported as `completeness`, and `RouteDecision.clarification_fields`
        # still carries what is missing -- but it no longer selects a stage. There
        # was a `clarification` node here; it could not do anything (see below).
        clarification_required = bool(route.clarification_fields)
        next_stage = "planner" if self._policy.should_plan(route) else "knowledge"
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

    # There was a `clarification` node here, between `router` and `planner`. It
    # spent a stage-timeout budget and one clarifier call per complex query to
    # produce values nothing read.
    #
    # It could not have done otherwise: the multi-round clarification state lives
    # in the session store behind `POST /api/v1/clarification/check`, so a graph
    # node has no collected context to pass and the clarifier therefore *always*
    # returned `action="ask"` -- which the node logged and then ignored,
    # continuing with the original question. Reaching into that session store from
    # here would have created a second, quieter definition of a clarification
    # round, which is the failure this repository already documents for the round
    # counter.
    #
    # `RouteDecision.clarification_fields` still carries what is missing, and the
    # HTTP endpoint still owns the interaction.

    async def planner(self, state: OrchestrationGraphState) -> dict[str, Any]:
        request = _required(state, "request", OrchestrationRequest)
        route = _required(state, "route", RouteDecision)
        plan, event = await self._run_stage(
            state,
            event_stage="plan",
            timeout_stage="plan",
            operation=lambda: self._services.planner(request, route),
            expected_type=TaskPlan,
            # Every downstream reader already handles an absent plan: retrieval
            # falls back to the original question and tools stay off.
            on_timeout=lambda: None,
        )
        return {"task_plan": plan, "trace": (event,)} if plan is not None else {"trace": (event,)}

    async def knowledge(self, state: OrchestrationGraphState) -> dict[str, Any]:
        request = _required(state, "request", OrchestrationRequest)
        route = _required(state, "route", RouteDecision)
        route_decision = _required(state, "route_decision", RouterDecision)
        plan = state.get("task_plan")
        retry_feedback = state.get("verification") if int(state.get("retry_count", 0)) > 0 else None
        # Source selection needs the scope for the same reason execution does:
        # whether the caller has any documents decides whether searching them can
        # produce anything. It was read 12 lines below for the retrieval call and
        # withheld from the decision about what to retrieve.
        strategy_scope = state.get("permission_scope")
        strategy, strategy_event = await self._run_stage(
            state,
            event_stage="knowledge_strategy",
            timeout_stage="knowledge_strategy",
            operation=lambda: self._services.knowledge_agent(
                request,
                route_decision,
                plan,
                retry_feedback,
                strategy_scope,
            ),
            expected_type=KnowledgeStrategy,
            # Source selection is a preference, not a prerequisite: fall back to
            # the local pair every route needs anyway.
            on_timeout=lambda: _timed_out_strategy(request.question),
        )
        scope = state.get("permission_scope")
        if scope is None:
            raise StageExecutionError("knowledge", PermissionError("knowledge retrieval requires access scope"))
        # One retrieval path. There used to be two -- an "orchestrator" branch
        # behind KNOWLEDGE_ORCHESTRATOR_ENABLED and a RAGAgentService branch --
        # and the disabled-by-default switch meant the branch that ran was the
        # one that discarded the strategy this node had just computed.
        context, event = await self._run_stage(
            state,
            event_stage="knowledge",
            timeout_stage="knowledge",
            operation=lambda: self._services.retriever(request, route, plan, strategy, scope),
            expected_type=ContextBundle,
            # No evidence, rather than no answer: synthesis already has a
            # documented no-evidence path and the verifier marks it degraded.
            on_timeout=ContextBundle,
        )
        # The context is built once, inside the orchestrator. This node used to
        # rebuild it from the returned items, running truncation and evidence
        # masking a second time and overwriting the first pass's diagnostics.
        evidence = EvidenceBundle(
            route=route,
            plan=plan,
            items=context.evidence,
            diagnostics=context.diagnostics,
        )
        tool_results: tuple[ToolResult, ...] = ()
        trace = [strategy_event, event]
        if plan is not None and self._policy.should_run_tools(route, plan):
            tool_results, tool_event = await self._run_stage(
                state,
                event_stage="tool",
                timeout_stage="tool",
                operation=lambda: self._services.tool_runner(request, route, plan),
                expected_type=tuple,
                validator=_validate_tool_results,
                # A tool that did not finish contributed nothing; the answer is
                # synthesized from the evidence alone.
                on_timeout=tuple,
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
            # `route` is not `_required` here: this node also runs on paths that
            # skipped routing, and the default skill is the right answer there.
            routed = state.get("route")
            skill = getattr(routed, "skill", "") or SKILL_DEFAULT
            candidate_answer, event = await self._run_stage(
                state,
                event_stage="synthesize",
                timeout_stage="synthesize",
                operation=lambda: candidate_synthesizer(request, context, tool_results, skill),
                expected_type=CandidateAnswer,
                # The same message synthesis itself returns when generation is
                # unavailable, so the client sees one failure mode, not two.
                on_timeout=_timed_out_candidate,
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

        budget = _required(state, "budget", ExecutionBudget)
        decision, verifier_event = await self._run_stage(
            state,
            event_stage="verifier",
            timeout_stage="verifier",
            operation=verification_operation,
            expected_type=VerificationDecision,
            # An unverified answer is a degraded answer, not a failed request.
            on_timeout=_timed_out_verification,
        )
        if decision.status == "retry_retrieval" and retry_count >= self._max_verifier_retries:
            decision = decision.model_copy(
                update={
                    "status": "degraded",
                    "retry_query": None,
                    "missing_aspects": tuple(decision.missing_aspects) + ("verifier retry budget exhausted",),
                }
            )
        if decision.status == "retry_retrieval" and not budget.has_budget(budget.config.retry_round_ms()):
            # Don't start a round the clock cannot pay for. A retry replays
            # knowledge + synthesis + verification; started without room for all
            # three it used to run into the total-budget check and turn a
            # degraded answer into a failed request.
            decision = decision.model_copy(
                update={
                    "status": "degraded",
                    "retry_query": None,
                    "missing_aspects": tuple(decision.missing_aspects)
                    + ("insufficient time budget for verifier retry",),
                }
            )
        if decision.status == "retry_retrieval":
            return {
                "verification": decision,
                "retry_count": retry_count + 1,
                "trace": (verifier_event,),
            }

        _record_routing_outcome(route, evidence, decision)
        cited_items = _items_for_references(candidate_answer.citations, evidence)
        base_answer = FinalAnswer(
            answer=candidate_answer.text,
            citations=tuple(_citation_label(item.source, item.page) for item in cited_items),
            route=route,
            evidence=evidence,
            evidence_ids=tuple(item.item_id for item in cited_items),
            # Carried to the public boundary: a governed write that is waiting on
            # confirmation has to be visible as a distinct outcome, not buried in
            # the answer text.
            tool_results=tuple(state.get("tool_results", ()) or ()),
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
                # Grounding, safety scan and the quality report are additive; the
                # verified answer is already complete without them.
                on_timeout=lambda: base_answer,
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
        request = _required(state, "request", OrchestrationRequest)
        scope = state.get("permission_scope")
        evidence = _required(state, "evidence_bundle", EvidenceBundle)
        budget = _required(state, "budget", ExecutionBudget)

        async def operation() -> FinalAnswer:
            if scope is None:
                raise PermissionError("output filtering requires an access scope")
            cited_ids = frozenset(answer.evidence_ids)
            cited_items = tuple(item for item in evidence.items if item.item_id in cited_ids)
            dlp = self._services.privacy.filter_output(answer.answer, cited_items, scope)
            # Number the markers only here, after DLP: this is the first point
            # that knows which citations actually survive into the response, so a
            # dropped one takes its marker with it instead of leaving a [n] that
            # resolves to nothing.  Index alignment holds because evidence.items
            # is the same tuple the synthesizer numbered its [E{k}] markers over;
            # the masked copies keep their item_id, so substituting them here
            # preserves it.
            masked_by_id = {item.item_id: item for item in dlp.citations}
            indexed = tuple(masked_by_id.get(item.item_id, item) for item in evidence.items)
            numbered, references = number_evidence_markers(
                dlp.answer,
                indexed,
                keep_item_ids=frozenset(masked_by_id),
            )
            # Every string the rendered list carries (source, page) is already
            # returned verbatim in `citations`, so appending it after inspection
            # discloses nothing this same response did not already carry.
            reference_list = render_reference_list(references, _reference_language(request, numbered))
            final_text = f"{numbered}\n\n{reference_list}" if reference_list else numbered
            labels = tuple(_citation_label(item.source, item.page) for item in references)
            # The full authorized set, not just what got cited. Narrowing
            # `evidence` to the citations made "retrieved context" and
            # "citations" the same list, so a caller could not see what the
            # answer had available and chose not to use.
            safe_evidence = evidence.model_copy(
                update={
                    "items": self._services.privacy.mask_context(evidence.items, scope),
                    "citations": labels,
                }
            )
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
                    "answer": final_text,
                    "citations": labels,
                    "evidence": safe_evidence,
                    "cited_evidence": references,
                    "evidence_ids": tuple(item.item_id for item in references),
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

        # No on_timeout: this stage is the output DLP boundary. Returning the
        # unfiltered answer would be a disclosure, not a degradation. It is
        # exempt from the total-budget gate (timeout_control.MANDATORY_STAGES)
        # so an exhausted budget upstream cannot squeeze it out.
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
        on_timeout: Callable[[], Any] | None = None,
    ) -> tuple[Any, ExecutionEvent]:
        """Run one stage under its ceiling, degrading rather than failing where it can.

        ``on_timeout`` supplies the value the run continues with when the stage
        exceeds its ceiling or the total budget is spent.  Without it a timeout
        propagates, which is correct only for the two stages where continuing
        would skip a security boundary -- ``privacy_permission`` and
        ``output_filter``.  Everywhere else a timeout used to become a bare 500
        even though a degraded answer was available.
        """

        budget = _required(state, "budget", ExecutionBudget)

        async def invoke() -> Any:
            return await run_with_timeout(timeout_stage, operation, budget)

        try:
            if self._monitor is not None:
                async with self._monitor.measure_async(f"orchestration_{event_stage}"):
                    result = await invoke()
            else:
                result = await invoke()
        except StageTimeoutError as exc:
            if on_timeout is None:
                raise
            logger.warning(
                "stage %s exceeded its %dms ceiling after %dms; continuing degraded",
                event_stage,
                exc.timeout_ms,
                exc.elapsed_ms,
            )
            event = ExecutionEvent(
                stage=event_stage,
                status="failed",
                duration_ms=int(budget.stage_times.get(timeout_stage, exc.elapsed_ms)),
                message=f"{event_stage} timed out; continuing with a degraded result",
                metadata=(EventMetadata(key="failure_reason", value=f"stage_timeout:{event_stage}"),),
            )
            await state["reporter"](event)
            return on_timeout(), event
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
    """Translate the route into the sources the Knowledge Agent must include.

    `hybrid` carries `graph` on purpose: it is the route that means "local
    retrieval *and* the graph", and leaving the hint out made it identical to
    `vector` unless the wording happened to trip a relationship keyword.
    """
    actual = route.effective_route
    if actual == "graph":
        return frozenset({"vector", "bm25", "graph"})
    if actual == "web":
        return frozenset({"vector", "bm25", "web"})
    if actual == "react":
        return frozenset({"vector", "bm25", "tool"})
    if actual == "hybrid":
        return frozenset({"vector", "bm25", "graph"})
    return frozenset({"vector", "bm25"})


def _citation_label(source: str, page: int | None) -> str:
    return f"{source}:{page}" if page is not None else source


def _record_routing_outcome(
    route: RouteDecision,
    evidence: EvidenceBundle,
    decision: VerificationDecision,
) -> None:
    """Close the router's calibration loop with an outcome it can be judged on.

    `record_routing_feedback` had no caller anywhere, so the calibrator never
    learned and `ENABLE_CALIBRATION` was a switch onto an empty distribution.

    Only outcomes actually attributable to *routing* are recorded. Retrieval
    finding nothing means the route pointed at the wrong sources; retrieval
    finding plenty and the verifier approving means it pointed at the right ones.
    An answer that had evidence and still came back degraded is a synthesis or
    validation problem, and scoring the router on it would train the calibrator
    on somebody else's failure -- so that case records nothing.
    """

    if route.raw_confidence is None:
        return
    if evidence.items:
        if decision.status != "approved":
            return
        was_correct = True
    else:
        was_correct = False
    try:
        from app.agents.router.routing import record_routing_feedback

        record_routing_feedback(route.raw_confidence, was_correct=was_correct)
    except Exception:  # pragma: no cover - telemetry must never fail a request
        logger.debug("routing calibration feedback was not recorded", exc_info=True)


def _timed_out_route() -> RouteDecision:
    """The safe route: local retrieval only, no plan, no tools."""
    return RouteDecision(
        intent="knowledge_retrieval",
        route="vector",
        confidence=0.0,
        requires_plan=False,
        allowed_capabilities=frozenset({"rag"}),
        reason="route_timeout_safe_default",
    )


def _timed_out_strategy(question: str) -> KnowledgeStrategy:
    """The local pair every route retrieves from anyway."""
    return KnowledgeStrategy(
        sources=tuple(
            KnowledgeSourcePlan(source=source, queries=(question,), top_k=6, timeout_ms=10_000, required=True)
            for source in ("vector", "bm25")
        ),
        rewrite=False,
        rerank=True,
        rationale="knowledge_strategy_timeout_local_default",
    )


def _timed_out_candidate() -> CandidateAnswer:
    from app.agents.synthesizer.generation import SYNTHESIS_FALLBACK_MESSAGE

    return CandidateAnswer(text=SYNTHESIS_FALLBACK_MESSAGE, unresolved_items=("synthesis_timeout",))


def _timed_out_verification() -> VerificationDecision:
    return VerificationDecision(status="degraded", missing_aspects=("verification timed out",))


def _reference_language(request: OrchestrationRequest, answer: str) -> str:
    """Pick the reference-list language from the explicit override, then the answer.

    The answer, not the question: the list is appended to the answer and has to
    read as part of it, and ``force_language`` may already have moved the answer
    away from the language the user typed in.
    """

    forced = str(getattr(request, "force_language", "") or "").strip().lower()
    if forced in {"zh", "en"}:
        return forced
    return "zh" if re.search(r"[一-鿿]", answer) else "en"


__all__ = ["WorkflowNodeRuntime", "WorkflowServices"]
