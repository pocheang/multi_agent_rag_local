"""The single typed orchestration execution owner."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from time import perf_counter
from typing import Any, Protocol

from app.domain.contracts import EvidenceBundle, FinalAnswer, RouteDecision, TaskPlan, ToolResult
from app.domain.errors import StageExecutionError
from app.domain.events import EventStage, ExecutionEvent
from app.orchestration.event_publisher import EventPublisher, NullEventPublisher
from app.orchestration.policies import ExecutionPolicy
from app.orchestration.request import OrchestrationRequest
from app.orchestration.standard_request_policy import (
    PreparedStandardRequest,
    bind_standard_runtime_context,
    prepare_standard_request,
)

Router = Callable[[OrchestrationRequest], Awaitable[RouteDecision]]
Planner = Callable[[OrchestrationRequest, RouteDecision], Awaitable[TaskPlan]]
Retriever = Callable[[OrchestrationRequest, RouteDecision, TaskPlan | None], Awaitable[EvidenceBundle]]
ToolRunner = Callable[[OrchestrationRequest, RouteDecision, TaskPlan, EvidenceBundle], Awaitable[tuple[ToolResult, ...]]]
Synthesizer = Callable[
    [OrchestrationRequest, RouteDecision, TaskPlan | None, EvidenceBundle, tuple[ToolResult, ...]],
    Awaitable[FinalAnswer],
]
Finalizer = Callable[[OrchestrationRequest, EvidenceBundle, FinalAnswer, ExecutionPolicy], Awaitable[FinalAnswer]]


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
        finalizer: Finalizer | None = None,
        context: object | None = None,
        event_reporter_binder: Callable[[Callable[[ExecutionEvent], Awaitable[None]]], None] | None = None,
    ) -> None:
        self.router = router
        self.planner = planner
        self.retriever = retriever
        self.tool_runner = tool_runner
        self.synthesizer = synthesizer
        self.finalizer = finalizer
        self.context = context
        self._event_reporter_binder = event_reporter_binder

    def bind_event_reporter(self, reporter: Callable[[ExecutionEvent], Awaitable[None]]) -> None:
        if self._event_reporter_binder is not None:
            self._event_reporter_binder(reporter)


class OrchestrationEngine:
    """Run one typed sequence; profiles only change ``ExecutionPolicy``."""

    def __init__(
        self,
        *,
        services: OrchestrationServices,
        publisher: EventPublisher | None = None,
        policy: ExecutionPolicy | None = None,
    ) -> None:
        self._services = services
        self._publisher = publisher or NullEventPublisher()
        self._policy = policy or ExecutionPolicy()
        self._services.bind_event_reporter(self._publisher.publish)

    def prepare_standard_request(self, request: OrchestrationRequest) -> PreparedStandardRequest:
        """Retain the request preparation seam without selecting a workflow."""
        return prepare_standard_request(request)

    def bind_standard_runtime_context(self, prepared: PreparedStandardRequest, **runtime_ports: Any) -> PreparedStandardRequest:
        return bind_standard_runtime_context(prepared, **runtime_ports)

    async def execute_prepared_standard(self, prepared: PreparedStandardRequest) -> FinalAnswer:
        request = prepared.request
        if prepared.early_response is not None:
            return FinalAnswer(answer=prepared.early_response.answer, route=RouteDecision(
                route=prepared.early_response.route,
                reason=prepared.early_response.reason,
                confidence=1.0,
                requires_plan=False,
                allowed_capabilities=frozenset({"rag"}),
            ))
        return await self.execute(request)

    async def execute_prepared_standard_stream(
        self,
        prepared: PreparedStandardRequest,
        *,
        execution_id: str,
        result_postprocessor: object | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        del result_postprocessor
        request = prepared.request.model_copy(update={"execution_id": execution_id})
        async for event in self.execute_stream(request):
            yield event

    async def execute(self, request: OrchestrationRequest) -> FinalAnswer:
        from app.services.runtime.retry_policy import retry_budget_scope

        with retry_budget_scope(request.retry_budget):
            return await self._execute(request)

    async def execute_stream(self, request: OrchestrationRequest, **_: Any) -> AsyncIterator[dict[str, Any]]:
        """Adapt the same typed execution into transport-neutral event dictionaries."""
        queue: asyncio.Queue[ExecutionEvent | FinalAnswer | Exception | None] = asyncio.Queue()

        async def publish(event: ExecutionEvent) -> None:
            await self._publisher.publish(event)
            await queue.put(event)

        async def run() -> None:
            try:
                from app.services.runtime.retry_policy import retry_budget_scope

                with retry_budget_scope(request.retry_budget):
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
        route = await self._run_stage("route", lambda: self._services.router(request), self._instance_validator(RouteDecision), reporter)
        self._policy.validate_route(route)
        plan = None
        if self._policy.should_plan(route):
            plan = await self._run_stage("plan", lambda: self._services.planner(request, route), self._instance_validator(TaskPlan), reporter)
        evidence = await self._run_stage("rag", lambda: self._services.retriever(request, route, plan), self._instance_validator(EvidenceBundle), reporter)
        tool_results: tuple[ToolResult, ...] = ()
        if self._policy.should_run_tools(route, plan):
            if plan is None:
                raise RuntimeError("tool execution requires a typed plan")
            tool_results = await self._run_stage("tool", lambda: self._services.tool_runner(request, route, plan, evidence), self._tool_results_validator, reporter)
        candidate = await self._run_stage(
            "synthesize",
            lambda: self._services.synthesizer(request, route, plan, evidence, tool_results),
            self._instance_validator(FinalAnswer),
            reporter,
        )
        finalizer = self._services.finalizer
        answer = candidate if finalizer is None else await finalizer(request, evidence, candidate, self._policy)
        if not isinstance(answer, FinalAnswer):
            raise TypeError("finalizer must return FinalAnswer")
        await reporter(ExecutionEvent(stage="complete", status="completed"))
        return answer

    async def _run_stage(self, stage: EventStage, operation: Callable[[], Awaitable[Any]], validator: Callable[[object], Any], reporter: Callable[[ExecutionEvent], Awaitable[None]]) -> Any:
        started = perf_counter()
        try:
            result = validator(await operation())
        except Exception as exc:
            await reporter(ExecutionEvent(stage="failed", status="failed", duration_ms=int((perf_counter() - started) * 1000), message=stage))
            raise StageExecutionError(stage, exc) from exc
        await reporter(ExecutionEvent(stage=stage, status="completed", duration_ms=int((perf_counter() - started) * 1000)))
        return result

    @staticmethod
    def _instance_validator(expected: type[Any]) -> Callable[[object], Any]:
        def validate(value: object) -> Any:
            if not isinstance(value, expected):
                raise TypeError(f"expected {expected.__name__}, got {type(value).__name__}")
            return value
        return validate

    @staticmethod
    def _tool_results_validator(value: object) -> tuple[ToolResult, ...]:
        if not isinstance(value, tuple) or not all(isinstance(item, ToolResult) for item in value):
            raise TypeError("expected a tuple of ToolResult values")
        return value


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
