"""Adapt citation-first synthesis to a typed FinalAnswer."""

from __future__ import annotations

import asyncio
import re
from collections.abc import Callable, Mapping

from app.agents.synthesizer.citations import normalize_answer_citations
from app.agents.synthesizer.generation import SYNTHESIS_FALLBACK_MESSAGE
from app.domain.contracts import EvidenceBundle, FinalAnswer, RouteDecision, TaskPlan, ToolResult
from app.domain.knowledge import EvidenceRef
from app.domain.workflow import CandidateAnswer, ContextBundle
from app.orchestration.request import OrchestrationRequest

SynthesisGenerator = Callable[..., object]
_EVIDENCE_MARKER_RE = re.compile(r"\[E(\d+)\]")


class SynthesizerAgentService:
    """Generate one answer from typed evidence and retain every citation label."""

    def __init__(self, generate: SynthesisGenerator | None = None) -> None:
        self._generate = generate or self._default_generate

    async def synthesize_candidate(
        self,
        request: OrchestrationRequest,
        context: ContextBundle,
        tool_results: tuple[ToolResult, ...],
    ) -> CandidateAnswer:
        """Generate once from governed context without retrieval, self-review, or DLP."""

        if not context.evidence and not tool_results:
            return CandidateAnswer(
                text=SYNTHESIS_FALLBACK_MESSAGE,
                unresolved_items=("no_evidence",),
            )

        allowed_labels = tuple(f"E{index}" for index in range(1, len(context.evidence) + 1))
        generation_context = context.rendered_context
        tool_context = _render_tool_results(tool_results)
        if tool_context:
            generation_context = f"{generation_context}\n\n{tool_context}".strip()
        generated = await asyncio.to_thread(
            self._generate,
            request.question,
            "answer_with_citations",
            memory_context=_render_conversation(request.conversation),
            vector_context=generation_context,
            force_language=request.force_language,
            session_id=request.session_id or "",
            enable_fact_verification=False,
            enable_self_review=False,
        )
        text = normalize_answer_citations(_answer_text(generated), allowed_labels)
        if not text:
            text = SYNTHESIS_FALLBACK_MESSAGE

        conflict_notes = tuple(str(value) for value in context.diagnostics.get("context_conflicts", ()) or ())
        if conflict_notes:
            disclosure = _conflict_disclosure(request.question)
            if disclosure not in text:
                text = f"{text}\n\n{disclosure}"

        references, unresolved = _references_from_markers(text, context)
        if context.evidence and not references:
            unresolved.append("missing_citations")
        if text == SYNTHESIS_FALLBACK_MESSAGE:
            unresolved.append("generation_fallback")
        return CandidateAnswer(
            text=text,
            citations=references,
            unresolved_items=tuple(dict.fromkeys(unresolved)),
        )

    async def synthesize(
        self,
        request: OrchestrationRequest,
        route: RouteDecision,
        plan: TaskPlan | None,
        evidence: EvidenceBundle,
        tool_results: tuple[ToolResult, ...],
    ) -> FinalAnswer:
        """Backward-compatible FinalAnswer adapter over the candidate interface."""

        del plan
        context = ContextBundle(
            evidence=evidence.items,
            rendered_context="\n\n".join(
                f"[E{index}] document={item.document_id}, page={item.page}; "
                f"source={item.source}; layer={item.layer}\n{item.content}"
                for index, item in enumerate(evidence.items, start=1)
            ),
            diagnostics=dict(evidence.diagnostics),
        )
        candidate = await self.synthesize_candidate(request, context, tool_results)
        text = candidate.text
        for index, item in reversed(tuple(enumerate(evidence.items, start=1))):
            text = text.replace(f"[E{index}]", f"[{_citation_label(item.source, item.page)}]")
        cited_ids = _evidence_ids_for_refs(candidate.citations, evidence)
        cited_id_set = frozenset(cited_ids)
        return FinalAnswer(
            answer=text,
            citations=tuple(
                _citation_label(item.source, item.page) for item in evidence.items if item.item_id in cited_id_set
            ),
            route=route,
            evidence=evidence,
            evidence_ids=cited_ids,
            unresolved_items=candidate.unresolved_items,
            execution_summary=f"evidence={len(evidence.items)} tool_results={len(tool_results)}",
        )

    @staticmethod
    def _default_generate(*args: object, **kwargs: object) -> object:
        from app.agents.synthesizer.generation import synthesize_answer

        return synthesize_answer(*args, **kwargs)


def _render_conversation(turns: tuple, *, max_turns: int = 12, max_chars: int = 4000) -> str:
    """Render recent conversation turns into the generator's memory_context slot.

    Bounded on both axes so a long session cannot crowd retrieved evidence out
    of the model's context window.  The newest turns are the ones kept.
    """
    if not turns:
        return ""
    recent = list(turns)[-max_turns:]
    lines = [
        f"{str(turn.role).strip() or 'user'}: {str(turn.content).strip()}"
        for turn in recent
        if str(getattr(turn, "content", "") or "").strip()
    ]
    if not lines:
        return ""
    rendered = "\n".join(lines)
    return rendered[-max_chars:] if len(rendered) > max_chars else rendered


def _answer_text(generated: object) -> str:
    if isinstance(generated, Mapping):
        return str(generated.get("answer", "") or "")
    return str(generated or "")


def _citation_label(source: str, page: int | None) -> str:
    return f"{source}:{page}" if page is not None else source


def _references_from_markers(
    text: str,
    context: ContextBundle,
) -> tuple[tuple[EvidenceRef, ...], list[str]]:
    references: list[EvidenceRef] = []
    unresolved: list[str] = []
    seen: set[int] = set()
    for raw_index in _EVIDENCE_MARKER_RE.findall(text):
        index = int(raw_index)
        if index in seen or index < 1 or index > len(context.evidence):
            continue
        seen.add(index)
        item = context.evidence[index - 1]
        if item.version is None:
            unresolved.append(f"unversioned_citation:E{index}")
            continue
        references.append(
            EvidenceRef(
                document_id=item.document_id,
                version=item.version,
                page=item.page,
                chunk_id=item.chunk_id,
                image_id=item.image_id,
            )
        )
    return tuple(references), unresolved


def _evidence_ids_for_refs(refs: tuple[EvidenceRef, ...], evidence: EvidenceBundle) -> tuple[str, ...]:
    keys = {(ref.document_id, ref.version, ref.page, ref.chunk_id, ref.image_id) for ref in refs}
    return tuple(
        item.item_id
        for item in evidence.items
        if (item.document_id, item.version, item.page, item.chunk_id, item.image_id) in keys
    )


def _render_tool_results(tool_results: tuple[ToolResult, ...]) -> str:
    summaries = [
        result.summary.strip() for result in tool_results if result.status == "succeeded" and result.summary.strip()
    ]
    if not summaries:
        return ""
    return "Governed tool results:\n" + "\n".join(
        f"Tool result {index}: {summary}" for index, summary in enumerate(summaries, start=1)
    )


def _conflict_disclosure(question: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", question):
        return "注：检索上下文存在派生知识与原始证据冲突；本答案以原始证据为准。"
    return "Note: Derived knowledge conflicted with original evidence; this answer follows the original evidence."


__all__ = ["SynthesisGenerator", "SynthesizerAgentService"]
