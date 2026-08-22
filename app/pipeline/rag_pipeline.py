"""Public typed pipeline boundary for every query profile."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, Protocol

from app.domain.contracts import FinalAnswer
from app.orchestration.capabilities import CoreCapabilities
from app.orchestration.engine import OrchestrationEngine
from app.orchestration.policies import ExecutionPolicy
from app.orchestration.standard_request_policy import PreparedStandardRequest
from app.pipeline.contracts import (
    DegradationEvent,
    PipelineCitation,
    PipelineContext,
    PipelineRequest,
    PipelineResult,
    PipelineRoute,
    to_orchestration_request,
)
from app.pipeline.profiles import PipelineProfile, get_profile_definition


def _parse_citation_label(label: str) -> PipelineCitation:
    """Parse citation label like 'doc1:5' into PipelineCitation with document_id and page."""
    if ":" in label:
        parts = label.rsplit(":", 1)
        try:
            return PipelineCitation(source=label, document_id=parts[0], page=int(parts[1]))
        except (ValueError, IndexError) as e:
            # Log parse failure but continue with fallback
            import logging

            logging.getLogger(__name__).debug(f"Failed to parse citation label '{label}': {e}. Using label as-is.")
    return PipelineCitation(source=label)


class PipelineExecutionEngine(Protocol):
    async def execute(self, request: Any) -> FinalAnswer: ...

    def execute_stream(self, request: Any, **kwargs: Any) -> AsyncIterator[dict[str, Any]]: ...


class RAGPipeline:
    """Translate public requests into one typed Engine and normalize its final answer."""

    def __init__(
        self,
        *,
        capabilities: CoreCapabilities | None = None,
        engine: PipelineExecutionEngine | None = None,
        tool_agent: object | None = None,
        **deprecated: Any,
    ) -> None:
        # Deprecated injection names are intentionally ignored.  They remain
        # accepted briefly so a stale caller cannot reactivate a legacy workflow.
        del deprecated
        if capabilities is None:
            capabilities = CoreCapabilities()
        if tool_agent is not None:
            capabilities.typed_tools = tool_agent
        self.capabilities = capabilities
        self._injected_engine = engine

    def _engine_for(self, profile: PipelineProfile) -> PipelineExecutionEngine:
        if self._injected_engine is not None:
            return self._injected_engine
        return OrchestrationEngine(
            services=self.capabilities.orchestration_services(),
            policy=ExecutionPolicy.for_profile(profile),
        )

    def capability_catalog(self) -> list[dict[str, str]]:
        """Expose the canonical capability set without compatibility imports."""
        return [
            {"name": "router", "description": "typed route selection"},
            {"name": "planner", "description": "typed task planning"},
            {"name": "retriever", "description": "evidence retrieval"},
            {"name": "tool_runner", "description": "governed tool execution"},
            {"name": "synthesizer", "description": "citation-first answer synthesis"},
            {"name": "finalizer", "description": "grounding, safety, validation, and quality"},
        ]

    async def _execute_compatibility(self, *_: Any, **__: Any) -> None:
        """Retired test seam; no production code invokes a compatibility executor."""
        raise RuntimeError("compatibility execution is retired")

    async def execute(self, request: PipelineRequest, profile: PipelineProfile | str | None = None) -> PipelineResult:
        selected = request.profile if profile is None else PipelineProfile(profile)
        if selected != request.profile:
            raise ValueError("Pipeline profile must match PipelineRequest.profile")
        get_profile_definition(selected)
        orchestration_request = to_orchestration_request(request)
        answer = await self._engine_for(selected).execute(orchestration_request)
        return self._result_from_final_answer(selected, answer)

    def execute_sync(self, request: PipelineRequest, profile: PipelineProfile | str | None = None) -> PipelineResult:
        return asyncio.run(self.execute(request, profile))

    async def execute_stream(
        self,
        request: PipelineRequest,
        *,
        execution_id: str,
        result_postprocessor: object | None = None,
    ) -> AsyncIterator[dict[str, Any]]:
        del result_postprocessor
        selected = request.profile
        get_profile_definition(selected)
        orchestration_request = to_orchestration_request(request).model_copy(update={"execution_id": execution_id})
        async for event in self._engine_for(selected).execute_stream(orchestration_request):
            yield event

    def prepare_standard_request(self, request: PipelineRequest) -> PreparedStandardRequest:
        """Compatibility request preparation; execution remains typed."""
        if request.profile is not PipelineProfile.STANDARD:
            raise ValueError("standard request preparation requires the standard profile")
        engine = self._engine_for(PipelineProfile.STANDARD)
        if not isinstance(engine, OrchestrationEngine):
            raise TypeError("an injected pipeline engine cannot prepare standard requests")
        return engine.prepare_standard_request(to_orchestration_request(request))

    def bind_standard_runtime_context(
        self, prepared: PreparedStandardRequest, **runtime_ports: Any
    ) -> PreparedStandardRequest:
        engine = self._engine_for(PipelineProfile.STANDARD)
        if not isinstance(engine, OrchestrationEngine):
            raise TypeError("an injected pipeline engine cannot bind standard runtime context")
        return engine.bind_standard_runtime_context(prepared, **runtime_ports)

    async def execute_prepared_standard(self, prepared: PreparedStandardRequest) -> PipelineResult:
        engine = self._engine_for(PipelineProfile.STANDARD)
        if not isinstance(engine, OrchestrationEngine):
            raise TypeError("an injected pipeline engine cannot execute prepared requests")
        return self._result_from_final_answer(
            PipelineProfile.STANDARD, await engine.execute_prepared_standard(prepared)
        )

    def execute_prepared_standard_sync(self, prepared: PreparedStandardRequest) -> PipelineResult:
        return asyncio.run(self.execute_prepared_standard(prepared))

    async def execute_prepared_standard_stream(
        self, prepared: PreparedStandardRequest, *, execution_id: str, result_postprocessor: object | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        del result_postprocessor
        engine = self._engine_for(PipelineProfile.STANDARD)
        if not isinstance(engine, OrchestrationEngine):
            raise TypeError("an injected pipeline engine cannot execute prepared streams")
        async for event in engine.execute_prepared_standard_stream(prepared, execution_id=execution_id):
            yield event

    @staticmethod
    def _result_from_final_answer(profile: PipelineProfile, answer: FinalAnswer) -> PipelineResult:
        # Prefer structured evidence items for citations (preserves document_id and page)
        if answer.evidence.items:
            citations = tuple(
                PipelineCitation(source=item.source, content=item.content, document_id=item.document_id, page=item.page)
                for item in answer.evidence.items
            )
        else:
            # Fallback: parse citation labels like "doc1:5" to extract document_id and page
            citations = tuple(_parse_citation_label(label) for label in answer.citations)
        contexts = tuple(
            PipelineContext(
                content=item.content,
                source=item.source,
                document_id=item.document_id,
                score=item.score,
            )
            for item in answer.evidence.items
        )
        quality = answer.quality_report.model_dump(mode="json") if answer.quality_report is not None else {}
        metadata = {
            **dict(answer.execution_metadata),
            "profile": profile.value,
            "execution_summary": answer.execution_summary,
            "evidence_ids": list(answer.evidence_ids),
            "validation": answer.validation.model_dump(mode="json"),
            "grounding": dict(answer.grounding),
            "safety": dict(answer.safety),
        }
        degradations = (
            ()
            if answer.validation.state == "validated"
            else (
                DegradationEvent(
                    stage="validation", reason="; ".join(answer.validation.issues) or answer.validation.state
                ),
            )
        )
        return PipelineResult(
            answer=answer.answer,
            citations=citations,
            route=PipelineRoute(
                route=answer.route.route or answer.route.intent,
                reason=answer.route.reason,
                confidence=answer.route.confidence,
            ),
            contexts=contexts,
            quality_report=quality,
            execution_metadata=metadata,
            degradation_events=degradations,
        )
