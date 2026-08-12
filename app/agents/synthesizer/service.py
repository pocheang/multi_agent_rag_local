"""Adapt citation-first synthesis to a typed FinalAnswer."""

from __future__ import annotations

import asyncio
from collections.abc import Callable, Mapping

from app.agents.synthesizer.citations import normalize_answer_citations
from app.agents.synthesizer.generation import SYNTHESIS_FALLBACK_MESSAGE
from app.domain.contracts import EvidenceBundle, FinalAnswer, RouteDecision, TaskPlan, ToolResult
from app.orchestration.request import OrchestrationRequest

SynthesisGenerator = Callable[..., object]


class SynthesizerAgentService:
    """Generate one answer from typed evidence and retain every citation label."""

    def __init__(self, generate: SynthesisGenerator | None = None) -> None:
        self._generate = generate or self._default_generate

    async def synthesize(
        self,
        request: OrchestrationRequest,
        route: RouteDecision,
        plan: TaskPlan | None,
        evidence: EvidenceBundle,
        tool_results: tuple[ToolResult, ...],
    ) -> FinalAnswer:
        """Call legacy synthesis once, then return only the immutable answer contract."""
        context = "\n\n".join(f"[{_citation_label(item.document_id, item.page)}] {item.content}" for item in evidence.items)
        generated = await asyncio.to_thread(
            self._generate,
            request.question,
            "answer_with_citations",
            vector_context=context,
            force_language=request.force_language,
            session_id=request.session_id or "",
            profile=request.profile,
        )
        citations = tuple(_citation_label(item.document_id, item.page) for item in evidence.items)
        text = normalize_answer_citations(_answer_text(generated), citations)
        if not citations and not text:
            text = SYNTHESIS_FALLBACK_MESSAGE
        if citations and not any(f"[{citation}]" in text for citation in citations):
            raise ValueError("evidence-backed answer must include a visible citation label")
        del plan
        return FinalAnswer(
            text=text,
            citations=citations,
            route=route,
            evidence_ids=evidence.item_ids,
            execution_summary=f"evidence={len(evidence.items)} tool_results={len(tool_results)}",
        )

    @staticmethod
    def _default_generate(*args: object, **kwargs: object) -> object:
        from app.agents.synthesizer.generation import synthesize_answer

        return synthesize_answer(*args, **kwargs)


def _answer_text(generated: object) -> str:
    if isinstance(generated, Mapping):
        return str(generated.get("answer", "") or "")
    return str(generated or "")


def _citation_label(document_id: str, page: int | None) -> str:
    return f"{document_id}:{page}" if page is not None else document_id
