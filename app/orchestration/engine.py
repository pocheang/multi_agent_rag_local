"""The single typed orchestration execution owner."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from contextvars import ContextVar
from typing import Any, Protocol

from app.core.config import get_settings
from app.domain.contracts import EvidenceBundle, FinalAnswer, RouteDecision, TaskPlan, ToolResult
from app.domain.events import ExecutionEvent
from app.domain.knowledge import KnowledgeStrategy
from app.domain.workflow import (
    CandidateAnswer,
    ClarificationResult,
    ContextBundle,
    RouterDecision,
    VerificationDecision,
)
from app.orchestration.event_publisher import EventPublisher, NullEventPublisher
from app.orchestration.execution_events import current_execution_id
from app.orchestration.langgraph.checkpoint import checkpoint_config
from app.orchestration.langgraph.workflow import build_workflow
from app.orchestration.policies import ExecutionPolicy
from app.orchestration.request import OrchestrationRequest
from app.orchestration.timeout_control import (
    ExecutionBudget,
    TimeoutConfig,
    get_timeout_config,
)
from app.privacy.service import PrivacyService
from app.services.security.access_scope import AccessScopeResolver

Router = Callable[[OrchestrationRequest], Awaitable[RouteDecision]]
Planner = Callable[[OrchestrationRequest, RouteDecision], Awaitable[TaskPlan]]
Retriever = Callable[[OrchestrationRequest, RouteDecision, TaskPlan | None], Awaitable[EvidenceBundle]]
ToolRunner = Callable[
    [OrchestrationRequest, RouteDecision, TaskPlan, EvidenceBundle], Awaitable[tuple[ToolResult, ...]]
]
Synthesizer = Callable[
    [OrchestrationRequest, RouteDecision, TaskPlan | None, EvidenceBundle, tuple[ToolResult, ...]],
    Awaitable[FinalAnswer],
]
CandidateSynthesizer = Callable[
    [OrchestrationRequest, ContextBundle, tuple[ToolResult, ...]],
    Awaitable[CandidateAnswer],
]
Finalizer = Callable[[OrchestrationRequest, EvidenceBundle, FinalAnswer, ExecutionPolicy], Awaitable[FinalAnswer]]
Clarifier = Callable[[OrchestrationRequest, RouterDecision], Awaitable[ClarificationResult]]
Verifier = Callable[
    [OrchestrationRequest, ContextBundle, CandidateAnswer, int],
    Awaitable[VerificationDecision],
]
KnowledgeAgent = Callable[
    [OrchestrationRequest, RouterDecision, TaskPlan | None, VerificationDecision | None],
    Awaitable[KnowledgeStrategy],
]
KnowledgeOrchestrator = Callable[
    [KnowledgeStrategy, Any, Callable[[ExecutionEvent], Awaitable[None]]],
    Awaitable[ContextBundle],
]


# Per-request event reporter, installed by the engine for the current async task.
# A ContextVar (not instance state) so one OrchestrationServices object can be
# shared across concurrent requests without one request's execution events
# leaking into another request's stream.  Mirrors the pattern already used by
# RAGAgentService for degradation reporting.
_current_event_reporter: ContextVar[Callable[[ExecutionEvent], Awaitable[None]] | None] = ContextVar(
    "orchestration_current_event_reporter", default=None
)


class CompatibilityStreamExecutor(Protocol):
    """Deprecated protocol retained only for import compatibility."""

    def __call__(self, *args: Any, **kwargs: Any) -> AsyncIterator[dict[str, Any]]: ...


class OrchestrationServices:
    """Canonical capabilities used by every profile."""

    def __init__(
        self,
        *,
        router: Router,
        planner: Planner,
        retriever: Retriever,
        tool_runner: ToolRunner,
        synthesizer: Synthesizer,
        candidate_synthesizer: CandidateSynthesizer | None = None,
        finalizer: Finalizer | None = None,
        clarifier: Clarifier | None = None,
        verifier: Verifier | None = None,
        knowledge_agent: KnowledgeAgent | None = None,
        knowledge_orchestrator: KnowledgeOrchestrator | None = None,
        privacy: PrivacyService | None = None,
        access_scope_resolver: AccessScopeResolver | None = None,
        context: object | None = None,
        event_reporter_binder: Callable[[Callable[[ExecutionEvent], Awaitable[None]]], None] | None = None,
    ) -> None:
        self.router = router
        self.planner = planner
        self.retriever = retriever
        self.tool_runner = tool_runner
        self.synthesizer = synthesizer
        self.candidate_synthesizer = candidate_synthesizer
        self.finalizer = finalizer
        self.clarifier = clarifier
        self.verifier = verifier
        self.knowledge_agent = knowledge_agent or _default_knowledge_agent
        self.knowledge_orchestrator = knowledge_orchestrator
        self.privacy = privacy or PrivacyService()
        self.access_scope_resolver = access_scope_resolver or AccessScopeResolver()
        self.context = context
        self._event_reporter_binder = event_reporter_binder

    def bind_event_reporter(self, reporter: Callable[[ExecutionEvent], Awaitable[None]]) -> None:
        """Install this request's reporter for the current async task only."""
        _current_event_reporter.set(reporter)
        if self._event_reporter_binder is not None:
            self._event_reporter_binder(reporter)

    async def report_event(self, event: ExecutionEvent) -> None:
        reporter = _current_event_reporter.get() or _discard_event
        await reporter(event)


class OrchestrationEngine:
    """Run one typed sequence; profiles only change ``ExecutionPolicy``."""

    def __init__(
        self,
        *,
        services: OrchestrationServices,
        publisher: EventPublisher | None = None,
        policy: ExecutionPolicy | None = None,
        timeout_config: TimeoutConfig | None = None,
        checkpointer: Any = None,
    ) -> None:
        self._services = services
        self._publisher = publisher or NullEventPublisher()
        self._policy = policy or ExecutionPolicy()
        self._timeout_config = timeout_config
        self._services.bind_event_reporter(self._publisher.publish)
        settings = get_settings()
        self._recursion_limit = settings.langgraph_recursion_limit
        try:
            from app.services.performance.monitor import get_monitor

            self._monitor = get_monitor()
        except Exception:
            self._monitor = None
        self._workflow = build_workflow(
            services,
            policy=self._policy,
            settings=settings,
            checkpointer=None,
            monitor=self._monitor,
        )
        self._checkpointed_workflow = (
            build_workflow(
                services,
                policy=self._policy,
                settings=settings,
                checkpointer=checkpointer,
                monitor=self._monitor,
            )
            if checkpointer is not None
            else None
        )

    async def execute(self, request: OrchestrationRequest) -> FinalAnswer:
        return await self._execute(request)

    async def execute_stream(self, request: OrchestrationRequest, **_: Any) -> AsyncIterator[dict[str, Any]]:
        """Adapt the same typed execution into transport-neutral event dictionaries."""
        queue: asyncio.Queue[ExecutionEvent | FinalAnswer | Exception | None] = asyncio.Queue()

        async def publish(event: ExecutionEvent) -> None:
            await self._publisher.publish(event)
            await queue.put(event)

        async def run() -> None:
            try:
                answer = await self._execute(request, publish=publish)
                await queue.put(answer)
            except Exception as exc:
                await queue.put(exc)
            finally:
                await queue.put(None)

        task = asyncio.create_task(run())
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                if isinstance(item, ExecutionEvent):
                    yield {"type": "status", "stage": item.stage, "status": item.status, "message": item.message}
                elif isinstance(item, Exception):
                    raise item
                else:
                    yield {"type": "done", "result": _terminal_payload(item)}
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def _execute(
        self,
        request: OrchestrationRequest,
        *,
        publish: Callable[[ExecutionEvent], Awaitable[None]] | None = None,
    ) -> FinalAnswer:
        reporter = publish or self._publisher.publish
        timeout_config = self._timeout_config or get_timeout_config(request.profile)
        budget = ExecutionBudget(timeout_config)
        self._services.bind_event_reporter(reporter)
        # Tell the publisher which execution these events belong to.  Scoped to
        # this task's context, and reset below, so a shared engine never files
        # one request's events under another request's id.
        execution_token = current_execution_id.set(request.execution_id)
        try:
            return await self._run_workflow(request, reporter, budget)
        finally:
            current_execution_id.reset(execution_token)

    async def _run_workflow(
        self,
        request: OrchestrationRequest,
        reporter: Callable[[ExecutionEvent], Awaitable[None]],
        budget: ExecutionBudget,
    ) -> FinalAnswer:
        persistence_config = checkpoint_config(request)
        workflow = self._workflow
        invoke_config: dict[str, Any] = {"recursion_limit": self._recursion_limit}
        if persistence_config is not None and self._checkpointed_workflow is not None:
            workflow = self._checkpointed_workflow
            invoke_config.update(persistence_config)
        result = await workflow.ainvoke(
            {
                "request": request,
                "retry_count": 0,
                "errors": (),
                "trace": (),
                "budget": budget,
                "reporter": reporter,
            },
            config=invoke_config,
        )
        answer = result.get("final_answer")
        if not isinstance(answer, FinalAnswer):
            raise RuntimeError("LangGraph workflow completed without FinalAnswer")
        from app.services.observability.workflow_diagnostics import summarize_workflow_execution

        workflow_diagnostics = summarize_workflow_execution(result)
        answer = answer.model_copy(
            update={
                "execution_metadata": {
                    **dict(answer.execution_metadata),
                    "workflow_diagnostics": workflow_diagnostics,
                }
            }
        )
        await reporter(
            ExecutionEvent(
                stage="complete",
                status="completed",
                duration_ms=int(workflow_diagnostics["total_stage_latency_ms"]),
            )
        )
        return answer


async def _discard_event(event: ExecutionEvent) -> None:
    del event


def _terminal_payload(answer: FinalAnswer) -> dict[str, Any]:
    return {
        "answer": answer.answer,
        "citations": list(answer.citations),
        "route": answer.route.effective_route,
        "validation": answer.validation.model_dump(mode="json"),
        "validation_status": answer.validation.state,
        "grounding": dict(answer.grounding),
        "safety": dict(answer.safety),
        "quality_report": answer.quality_report.model_dump(mode="json") if answer.quality_report is not None else None,
        "execution_metadata": dict(answer.execution_metadata),
    }


async def _default_knowledge_agent(
    request: OrchestrationRequest,
    route: RouterDecision,
    plan: TaskPlan | None,
    retry_feedback: VerificationDecision | None,
) -> KnowledgeStrategy:
    """Lazy compatibility default that avoids orchestration import cycles."""

    from app.agents.knowledge.service import KnowledgeAgentService

    return await KnowledgeAgentService().decide(request, route, plan, retry_feedback)
