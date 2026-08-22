"""The single typed orchestration execution owner."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any, Protocol

from app.domain.contracts import EvidenceBundle, FinalAnswer, RouteDecision, TaskPlan, ToolResult
from app.domain.errors import StageExecutionError
from app.domain.events import ExecutionEvent
from app.orchestration.event_publisher import EventPublisher, NullEventPublisher
from app.orchestration.policies import ExecutionPolicy
from app.orchestration.request import OrchestrationRequest
from app.orchestration.standard_request_policy import (
    PreparedStandardRequest,
    bind_standard_runtime_context,
    prepare_standard_request,
)
from app.orchestration.timeout_control import (
    ExecutionBudget,
    TimeoutConfig,
    get_timeout_config,
    run_with_timeout,
)

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
        timeout_config: TimeoutConfig | None = None,
    ) -> None:
        self._services = services
        self._publisher = publisher or NullEventPublisher()
        self._policy = policy or ExecutionPolicy()
        self._timeout_config = timeout_config
        self._services.bind_event_reporter(self._publisher.publish)

        # Initialize performance monitoring
        try:
            from app.services.performance.monitor import get_monitor

            self._monitor = get_monitor()
        except Exception:
            self._monitor = None

    def prepare_standard_request(self, request: OrchestrationRequest) -> PreparedStandardRequest:
        """Retain the request preparation seam without selecting a workflow."""
        return prepare_standard_request(request)

    def bind_standard_runtime_context(
        self, prepared: PreparedStandardRequest, **runtime_ports: Any
    ) -> PreparedStandardRequest:
        return bind_standard_runtime_context(prepared, **runtime_ports)

    async def execute_prepared_standard(self, prepared: PreparedStandardRequest) -> FinalAnswer:
        request = prepared.request
        if prepared.early_response is not None:
            return FinalAnswer(
                answer=prepared.early_response.answer,
                route=RouteDecision(
                    route=prepared.early_response.route,
                    reason=prepared.early_response.reason,
                    confidence=1.0,
                    requires_plan=False,
                    allowed_capabilities=frozenset({"rag"}),
                ),
            )
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

        # Initialize execution budget with timeout control
        timeout_config = self._timeout_config or get_timeout_config(request.profile)
        budget = ExecutionBudget(timeout_config)

        # Stage 1: Route
        route = await self._execute_stage_with_optional_monitoring(
            stage="route",
            operation=lambda: self._services.router(request),
            expected_type=RouteDecision,
            budget=budget,
            reporter=reporter,
        )
        self._policy.validate_route(route)

        # Stage 2: Plan (optional)
        plan = None
        if self._policy.should_plan(route):
            plan = await self._execute_stage_with_optional_monitoring(
                stage="plan",
                operation=lambda: self._services.planner(request, route),
                expected_type=TaskPlan,
                budget=budget,
                reporter=reporter,
            )

        # Stage 3: Retrieval
        evidence = await self._execute_stage_with_optional_monitoring(
            stage="rag",
            operation=lambda: self._services.retriever(request, route, plan),
            expected_type=EvidenceBundle,
            budget=budget,
            reporter=reporter,
        )

        # Stage 4: Tool execution (optional)
        tool_results: tuple[ToolResult, ...] = ()
        if self._policy.should_run_tools(route, plan):
            tool_results = await self._execute_stage(
                stage="tool",
                operation=lambda: self._services.tool_runner(request, route, plan, evidence),
                expected_type=tuple,
                budget=budget,
                reporter=reporter,
                custom_validator=self._validate_tool_results,
            )

        # Stage 5: Synthesis
        candidate = await self._execute_stage_with_optional_monitoring(
            stage="synthesize",
            operation=lambda: self._services.synthesizer(request, route, plan, evidence, tool_results),
            expected_type=FinalAnswer,
            budget=budget,
            reporter=reporter,
        )

        # Stage 6: Finalization (optional)
        finalizer = self._services.finalizer
        if finalizer is not None:
            answer = await self._execute_stage_with_optional_monitoring(
                stage="finalize",
                operation=lambda: finalizer(request, evidence, candidate, self._policy),
                expected_type=FinalAnswer,
                budget=budget,
                reporter=reporter,
            )
        else:
            answer = candidate

        # Add budget statistics to execution metadata
        answer = answer.model_copy(
            update={
                "execution_metadata": {
                    **(answer.execution_metadata or {}),
                    "budget_stats": budget.get_stats(),
                }
            }
        )

        await reporter(ExecutionEvent(stage="complete", status="completed"))
        return answer

    async def _execute_stage(
        self,
        stage: str,
        operation: Callable[[], Awaitable[Any]],
        expected_type: type[Any],
        budget: ExecutionBudget,
        reporter: Callable[[ExecutionEvent], Awaitable[None]],
        *,
        custom_validator: Callable[[Any], Any] | None = None,
    ) -> Any:
        """Execute a single pipeline stage with timeout, validation, and event reporting.

        Args:
            stage: Stage name for timeout tracking and events
            operation: Async operation to execute
            expected_type: Expected return type for validation
            budget: Execution budget for timeout control
            reporter: Event reporter for stage completion
            custom_validator: Optional custom validation function (overrides type check)

        Returns:
            Validated stage result

        Raises:
            TimeoutError: If stage exceeds timeout budget
            StageExecutionError: If stage fails validation or execution
        """
        # run_with_timeout() already calls budget.check_budget() internally
        result = await run_with_timeout(stage, operation, budget)

        # Validate result type
        try:
            if custom_validator is not None:
                result = custom_validator(result)
            elif not isinstance(result, expected_type):
                raise TypeError(f"expected {expected_type.__name__}, got {type(result).__name__}")
        except Exception as exc:
            # Wrap validation errors in StageExecutionError for consistency
            raise StageExecutionError(stage, exc) from exc

        await reporter(
            ExecutionEvent(
                stage=stage,
                status="completed",
                duration_ms=budget.stage_times.get(stage, 0),
            )
        )
        return result

    async def _execute_stage_with_optional_monitoring(
        self,
        stage: str,
        operation: Callable[[], Awaitable[Any]],
        expected_type: type[Any],
        budget: ExecutionBudget,
        reporter: Callable[[ExecutionEvent], Awaitable[None]],
        *,
        custom_validator: Callable[[Any], Any] | None = None,
    ) -> Any:
        """Execute stage with optional performance monitoring.

        Wraps _execute_stage with monitor.measure_async if monitor is available.
        This eliminates code duplication from the if/else monitoring pattern.

        Args:
            Same as _execute_stage

        Returns:
            Stage execution result
        """
        if self._monitor:
            # Map stage names to monitor metric names
            metric_name = f"orchestration_{stage}"
            async with self._monitor.measure_async(metric_name):
                return await self._execute_stage(
                    stage=stage,
                    operation=operation,
                    expected_type=expected_type,
                    budget=budget,
                    reporter=reporter,
                    custom_validator=custom_validator,
                )
        else:
            return await self._execute_stage(
                stage=stage,
                operation=operation,
                expected_type=expected_type,
                budget=budget,
                reporter=reporter,
                custom_validator=custom_validator,
            )

    @staticmethod
    def _validate_tool_results(value: Any) -> tuple[ToolResult, ...]:
        """Validate tool results are a tuple of ToolResult instances."""
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
