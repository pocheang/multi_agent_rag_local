"""Enhanced orchestration engine with user-friendly progress tracking."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from app.domain.contracts import EvidenceBundle, FinalAnswer, RouteDecision, TaskPlan, ToolResult
from app.domain.events import ExecutionEvent
from app.domain.user_experience import (
    AnswerQualityCard,
    QualityCardBuilder,
    UserFriendlyProgress,
    convert_to_user_friendly_error,
)
from app.orchestration.event_publisher import EventPublisher, NullEventPublisher
from app.orchestration.policies import ExecutionPolicy
from app.orchestration.request import OrchestrationRequest
from app.orchestration.timeout_control import (
    ExecutionBudget,
    TimeoutConfig,
    get_timeout_config,
    run_with_timeout,
)

logger = logging.getLogger(__name__)

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


class EnhancedOrchestrationEngine:
    """Enhanced orchestration engine with user-friendly progress tracking."""

    def __init__(
        self,
        *,
        services: OrchestrationServices,
        publisher: EventPublisher | None = None,
        policy: ExecutionPolicy | None = None,
        timeout_config: TimeoutConfig | None = None,
        enable_user_friendly_progress: bool = True,
    ) -> None:
        self._services = services
        self._publisher = publisher or NullEventPublisher()
        self._policy = policy or ExecutionPolicy()
        self._timeout_config = timeout_config
        self._enable_user_friendly = enable_user_friendly_progress
        self._services.bind_event_reporter(self._publisher.publish)

    async def execute_stream(self, request: OrchestrationRequest, **_: Any) -> AsyncIterator[dict[str, Any]]:
        """Stream execution with user-friendly progress updates."""

        queue: asyncio.Queue[ExecutionEvent | FinalAnswer | Exception | None] = asyncio.Queue()

        async def publish_with_translation(event: ExecutionEvent) -> None:
            """Publish both internal and user-friendly events."""
            # Publish internal event
            await self._publisher.publish(event)

            # Publish user-friendly progress if enabled
            if self._enable_user_friendly:
                try:
                    user_progress = UserFriendlyProgress.from_execution_event(
                        stage=event.stage,
                        status=event.status,
                        message=event.message,
                        language=request.force_language or "zh",
                    )

                    # Create a user-friendly event
                    user_event = ExecutionEvent(
                        stage=event.stage,
                        status=event.status,
                        message=user_progress.user_message,
                        progress_percent=user_progress.progress_percent,
                        estimated_seconds=user_progress.estimated_seconds,
                    )
                    await queue.put(user_event)
                except Exception as e:
                    logger.warning(f"Failed to translate progress: {e}")
                    await queue.put(event)
            else:
                await queue.put(event)

        async def run() -> None:
            try:
                from app.services.runtime.retry_policy import retry_budget_scope

                with retry_budget_scope(request.retry_budget):
                    answer = await self._execute_with_quality_card(request, publish=publish_with_translation)
                await queue.put(answer)
            except Exception as exc:
                # Convert to user-friendly error
                if self._enable_user_friendly:
                    user_error = convert_to_user_friendly_error(exc, language=request.force_language or "zh")
                    # Create a user-friendly error event
                    error_event = ExecutionEvent(
                        stage="error",
                        status="failed",
                        message=user_error.format_for_display(),
                    )
                    await queue.put(error_event)
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
                    event_dict = {
                        "type": "status",
                        "stage": item.stage,
                        "status": item.status,
                        "message": item.message,
                    }
                    # Include progress info if available
                    if hasattr(item, "progress_percent") and item.progress_percent is not None:
                        event_dict["progress_percent"] = item.progress_percent
                    if hasattr(item, "estimated_seconds") and item.estimated_seconds is not None:
                        event_dict["estimated_seconds"] = item.estimated_seconds

                    yield event_dict
                elif isinstance(item, Exception):
                    raise item
                else:
                    # Final answer with quality card
                    result_dict = _terminal_payload(item)

                    # Add formatted quality card if available
                    if item.quality_card:
                        result_dict["quality_card"] = item.quality_card.to_user_display(
                            language=request.force_language or "zh"
                        )
                        result_dict["quality_card_text"] = item.quality_card.format_as_text(
                            language=request.force_language or "zh"
                        )

                    yield {"type": "done", "result": result_dict}
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def _execute_with_quality_card(
        self,
        request: OrchestrationRequest,
        *,
        publish: Callable[[ExecutionEvent], Awaitable[None]] | None = None,
    ) -> FinalAnswer:
        """Execute pipeline and add quality card to final answer."""

        reporter = publish or self._publisher.publish
        timeout_config = self._timeout_config or get_timeout_config(request.profile)
        budget = ExecutionBudget(timeout_config)

        # Stage 1: Route
        route = await self._execute_stage(
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
            plan = await self._execute_stage(
                stage="plan",
                operation=lambda: self._services.planner(request, route),
                expected_type=TaskPlan,
                budget=budget,
                reporter=reporter,
            )

        # Stage 3: Retrieval
        evidence = await self._execute_stage(
            stage="rag",
            operation=lambda: self._services.retriever(request, route, plan),
            expected_type=EvidenceBundle,
            budget=budget,
            reporter=reporter,
        )

        # Stage 4: Tool execution (optional)
        tool_results: tuple[ToolResult, ...] = ()
        if self._policy.should_run_tools(route, plan):
            if plan is None:
                raise RuntimeError("tool execution requires a typed plan")
            tool_results = await self._execute_stage(
                stage="tool",
                operation=lambda: self._services.tool_runner(request, route, plan, evidence),
                expected_type=tuple,
                budget=budget,
                reporter=reporter,
                custom_validator=self._validate_tool_results,
            )

        # Stage 5: Synthesis
        candidate = await self._execute_stage(
            stage="synthesize",
            operation=lambda: self._services.synthesizer(request, route, plan, evidence, tool_results),
            expected_type=FinalAnswer,
            budget=budget,
            reporter=reporter,
        )

        # Stage 6: Finalization (optional)
        finalizer = self._services.finalizer
        if finalizer is not None:
            answer = await self._execute_stage(
                stage="finalize",
                operation=lambda: finalizer(request, evidence, candidate, self._policy),
                expected_type=FinalAnswer,
                budget=budget,
                reporter=reporter,
            )
        else:
            answer = candidate

        # Build quality card
        quality_card = self._build_quality_card(answer, evidence)

        # Add quality card and budget stats to answer
        answer = answer.model_copy(
            update={
                "quality_card": quality_card,
                "execution_metadata": {
                    **dict(answer.execution_metadata),
                    "budget_stats": budget.get_stats(),
                },
            }
        )

        await reporter(ExecutionEvent(stage="complete", status="completed"))
        return answer

    def _build_quality_card(
        self,
        answer: FinalAnswer,
        evidence: EvidenceBundle,
    ) -> AnswerQualityCard:
        """Build user-friendly quality card from answer validation results."""

        builder = QualityCardBuilder()

        # Extract validation score
        validation_score = answer.validation.approved if hasattr(answer.validation, "approved") else 0.5

        # Extract citation completeness
        citation_count = len(answer.citations)
        evidence_count = len(evidence.items)
        citation_completeness = min(1.0, citation_count / max(1, evidence_count))

        # Extract retrieval scores
        retrieval_scores = [item.score for item in evidence.items if item.score is not None]

        # Check for validation issues
        has_issues = len(answer.validation.issues) > 0 if hasattr(answer.validation, "issues") else False

        # Generate suggestions based on answer content
        suggestions, limitations = self._generate_contextual_guidance(answer, evidence)

        quality_card = builder.build_from_answer(
            validation_score=validation_score,
            evidence_count=evidence_count,
            citation_completeness=citation_completeness,
            retrieval_scores=retrieval_scores,
            has_validation_issues=has_issues,
        )

        # Override with contextual suggestions if available
        if suggestions or limitations:
            quality_card = quality_card.model_copy(
                update={
                    "suggestions": tuple(suggestions) if suggestions else quality_card.suggestions,
                    "limitations": tuple(limitations) if limitations else quality_card.limitations,
                }
            )

        return quality_card

    def _generate_contextual_guidance(
        self,
        answer: FinalAnswer,
        evidence: EvidenceBundle,
    ) -> tuple[list[str], list[str]]:
        """Generate context-aware suggestions and limitations."""

        suggestions = []
        limitations = []

        # Check if answer mentions specific years/dates
        import re

        year_pattern = r"\b(19|20)\d{2}\b"
        years_mentioned = set(re.findall(year_pattern, answer.answer))

        if years_mentioned:
            latest_year = max(int(y) for y in years_mentioned)
            if latest_year < 2024:
                limitations.append(f"数据截至{latest_year}年，可能不包含最新信息")

        # Check evidence source diversity
        source_types = set(item.source for item in evidence.items)
        if len(source_types) == 1:
            limitations.append("仅使用了单一来源的信息")
            suggestions.append("如需更全面的视角，可尝试不同的提问方式")

        return suggestions, limitations

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
        """Execute a single pipeline stage with timeout, validation, and event reporting."""

        result = await run_with_timeout(stage, operation, budget)

        # Validate result type
        if custom_validator is not None:
            result = custom_validator(result)
        elif not isinstance(result, expected_type):
            raise TypeError(f"expected {expected_type.__name__}, got {type(result).__name__}")

        await reporter(
            ExecutionEvent(
                stage=stage,
                status="completed",
                duration_ms=budget.stage_times.get(stage, 0),
            )
        )
        return result

    @staticmethod
    def _validate_tool_results(value: Any) -> tuple[ToolResult, ...]:
        """Validate tool results are a tuple of ToolResult instances."""
        if not isinstance(value, tuple) or not all(isinstance(item, ToolResult) for item in value):
            raise TypeError("expected a tuple of ToolResult values")
        return value


def _terminal_payload(answer: FinalAnswer) -> dict[str, Any]:
    """Convert final answer to API payload."""
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
