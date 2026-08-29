"""Public typed pipeline boundary for every query profile."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any, Protocol

from app.domain.contracts import FinalAnswer
from app.orchestration.capabilities import CoreCapabilities
from app.orchestration.engine import OrchestrationEngine
from app.orchestration.policies import ExecutionPolicy
from app.pipeline.contracts import (
    DegradationEvent,
    PipelineCitation,
    PipelineContext,
    PipelineRequest,
    PipelineResult,
    PipelineRoute,
    to_orchestration_request,
)
from app.pipeline.profiles import PipelineProfile


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


# One compiled LangGraph workflow per profile.  Building it costs ~20ms of
# synchronous CPU work, which would otherwise run on the event loop for every
# request.  Safe to share only because OrchestrationServices scopes its event
# reporter with a ContextVar (see app/orchestration/engine.py); without that,
# concurrent requests would overwrite each other's event stream.
_ENGINE_CACHE: dict[PipelineProfile, PipelineExecutionEngine] = {}


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
        self._uses_default_capabilities = capabilities is None and tool_agent is None
        if capabilities is None:
            capabilities = CoreCapabilities()
        if tool_agent is not None:
            capabilities.typed_tools = tool_agent
        self.capabilities = capabilities
        self._injected_engine = engine

    def _engine_for(self, profile: PipelineProfile) -> PipelineExecutionEngine:
        if self._injected_engine is not None:
            return self._injected_engine
        if not self._uses_default_capabilities:
            # Custom capabilities must not be served from (or poison) the shared
            # cache; build a private engine instead.
            return self._build_engine(profile)
        engine = _ENGINE_CACHE.get(profile)
        if engine is None:
            engine = self._build_engine(profile)
            _ENGINE_CACHE[profile] = engine
        return engine

    def _build_engine(self, profile: PipelineProfile) -> PipelineExecutionEngine:
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
        orchestration_request = to_orchestration_request(request).model_copy(update={"execution_id": execution_id})
        async for event in self._engine_for(selected).execute_stream(orchestration_request):
            yield event

    @staticmethod
    def _result_from_final_answer(profile: PipelineProfile, answer: FinalAnswer) -> PipelineResult:
        # Prefer structured evidence items for citations (preserves document_id and page)
        if answer.evidence.items:
            citations = tuple(
                PipelineCitation(
                    source=item.source,
                    content=item.content,
                    document_id=item.document_id,
                    version=item.version,
                    page=item.page,
                    chunk_id=item.chunk_id,
                    image_id=item.image_id,
                    artifact_uri=item.artifact_uri,
                    modality=item.modality,
                    layer=item.layer,
                    metadata={"acl_tags": sorted(item.acl_tags)} if item.acl_tags else {},
                )
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
                version=item.version,
                page=item.page,
                chunk_id=item.chunk_id,
                image_id=item.image_id,
                artifact_uri=item.artifact_uri,
                modality=item.modality,
                layer=item.layer,
                score=item.score,
                metadata={"acl_tags": sorted(item.acl_tags)} if item.acl_tags else {},
            )
            for item in answer.evidence.items
        )
        quality = answer.quality_report.model_dump(mode="json") if answer.quality_report is not None else {}
        plan = answer.evidence.plan
        metadata = {
            **dict(answer.execution_metadata),
            "profile": profile.value,
            "execution_summary": answer.execution_summary,
            "evidence_ids": list(answer.evidence_ids),
            "validation": answer.validation.model_dump(mode="json"),
            "grounding": dict(answer.grounding),
            "safety": dict(answer.safety),
            "plan": (
                None
                if plan is None
                else {
                    "tasks": [
                        {"task_id": task.task_id, "prompt": task.prompt, "depends_on": list(task.depends_on)}
                        for task in plan.tasks
                    ],
                    "fallback_reason": plan.plan_fallback_reason,
                }
            ),
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
