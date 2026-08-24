"""Single execution owner for all knowledge retrieval sources."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass

from app.core.config import Settings, get_settings
from app.domain.contracts import EvidenceItem
from app.domain.events import EventMetadata, ExecutionEvent
from app.domain.knowledge import AccessScope, KnowledgeSource, KnowledgeSourcePlan, KnowledgeStrategy
from app.domain.workflow import ContextBundle
from app.knowledge.adapters import KnowledgeAdapter, build_default_adapters
from app.knowledge.context import ContextBuilder
from app.knowledge.deduplication import deduplicate_evidence
from app.knowledge.fusion import reciprocal_rank_fuse, rerank_evidence
from app.privacy.dlp import mask_evidence
from app.services.query_rewrite import build_rewrite_queries

TraceReporter = Callable[[ExecutionEvent], Awaitable[None]]
QueryRewriter = Callable[[str], Sequence[str]]


@dataclass(frozen=True)
class _SourceOutcome:
    source: KnowledgeSource
    items: tuple[EvidenceItem, ...]
    duration_ms: int
    status: str
    error_type: str | None = None
    scope_dropped: int = 0


class KnowledgeOrchestrator:
    """Rewrite once, retrieve selected sources concurrently, then build safe context."""

    def __init__(
        self,
        *,
        adapters: Mapping[KnowledgeSource, KnowledgeAdapter] | None = None,
        rewriter: QueryRewriter | None = None,
        settings: Settings | None = None,
    ) -> None:
        active = settings or get_settings()
        self._adapters = dict(adapters or build_default_adapters())
        self._rrf_k = active.hybrid_rrf_k
        self._reranker_top_n = active.reranker_top_n
        self._reranker_timeout_ms = active.knowledge_reranker_timeout_ms
        self._reranker_enabled = active.enable_reranker
        self._context_builder = ContextBuilder(token_budget=active.knowledge_context_token_budget)
        self._rewrite = rewriter or (
            lambda query: build_rewrite_queries(
                query,
                enable_llm=bool(active.query_rewrite_enabled and active.query_rewrite_with_llm),
                enable_decompose=False,
                max_variants=active.query_rewrite_max_variants,
            )
        )

    async def retrieve(
        self,
        strategy: KnowledgeStrategy,
        scope: AccessScope,
        trace: TraceReporter,
    ) -> ContextBundle:
        """Execute only selected sources with bounded timeouts and explicit diagnostics."""

        started = time.perf_counter()
        rewritten, rewrite_diagnostics = await self._rewrite_once(strategy)
        source_plans = tuple(self._with_queries(plan, rewritten) for plan in strategy.sources)
        outcomes = await asyncio.gather(
            *(self._retrieve_source(plan, scope) for plan in source_plans),
        )
        trace_failures = 0
        for outcome in outcomes:
            try:
                await trace(_outcome_event(outcome))
            except asyncio.CancelledError:
                raise
            except Exception:
                trace_failures += 1

        ranked_lists = tuple(outcome.items for outcome in outcomes if outcome.status == "completed")
        fused = reciprocal_rank_fuse(ranked_lists, rrf_k=self._rrf_k)
        deduplicated = deduplicate_evidence(fused)
        primary_query = strategy.sources[0].queries[0]
        if strategy.rerank:
            reranked, reranker_diagnostics = await rerank_evidence(
                primary_query,
                deduplicated,
                top_n=self._reranker_top_n,
                timeout_ms=self._reranker_timeout_ms,
                enabled=self._reranker_enabled,
            )
        else:
            reranked = deduplicated[: self._reranker_top_n]
            reranker_diagnostics = {
                "reranker_backend": "skipped",
                "reranker_fallback_reason": "strategy_disabled",
            }

        failed = tuple(outcome.source for outcome in outcomes if outcome.status != "completed")
        required_failures = tuple(
            plan.source
            for plan, outcome in zip(source_plans, outcomes, strict=True)
            if plan.required and outcome.status != "completed"
        )
        diagnostics: dict[str, object] = {
            **rewrite_diagnostics,
            "selected_sources": tuple(plan.source for plan in source_plans),
            "adapter_count": len(source_plans),
            "source_status": {outcome.source: outcome.status for outcome in outcomes},
            "source_duration_ms": {outcome.source: outcome.duration_ms for outcome in outcomes},
            "source_result_count": {outcome.source: len(outcome.items) for outcome in outcomes},
            "retrieval_scope_dropped": sum(outcome.scope_dropped for outcome in outcomes),
            "trace_report_failures": trace_failures,
            "failed_sources": failed,
            "required_source_failures": required_failures,
            "pre_fusion_count": sum(len(items) for items in ranked_lists),
            "post_rrf_count": len(fused),
            "post_dedup_count": len(deduplicated),
            "rrf_k": self._rrf_k,
            **reranker_diagnostics,
            "post_rerank_count": len(reranked),
            "knowledge_duration_ms": int((time.perf_counter() - started) * 1000),
        }
        return self._context_builder.build(reranked, scope, diagnostics=diagnostics)

    async def _rewrite_once(self, strategy: KnowledgeStrategy) -> tuple[tuple[str, ...], dict[str, object]]:
        primary = strategy.sources[0].queries[0]
        if not strategy.rewrite:
            return (primary,), {
                "rewrite_invocations": 0,
                "rewrite_backend": "disabled",
                "rewrite_fallback_reason": None,
                "rewritten_queries": (primary,),
            }
        try:
            values = await asyncio.to_thread(self._rewrite, primary)
            rewritten = _unique_queries(values) or (primary,)
            return rewritten, {
                "rewrite_invocations": 1,
                "rewrite_backend": "configured",
                "rewrite_fallback_reason": None,
                "rewritten_queries": rewritten,
            }
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return (primary,), {
                "rewrite_invocations": 1,
                "rewrite_backend": "original_query",
                "rewrite_fallback_reason": type(exc).__name__,
                "rewritten_queries": (primary,),
            }

    @staticmethod
    def _with_queries(plan: KnowledgeSourcePlan, rewritten: tuple[str, ...]) -> KnowledgeSourcePlan:
        return plan.model_copy(update={"queries": _unique_queries((*plan.queries, *rewritten))})

    async def _retrieve_source(self, plan: KnowledgeSourcePlan, scope: AccessScope) -> _SourceOutcome:
        started = time.perf_counter()
        adapter = self._adapters.get(plan.source)
        if plan.source in {"vector", "bm25", "graph", "wiki", "multimodal"} and not (
            scope.document_ids or scope.allowed_sources
        ):
            return _SourceOutcome(
                source=plan.source,
                items=(),
                duration_ms=0,
                status="skipped",
                error_type="EmptyAccessScope",
            )
        if adapter is None:
            return _SourceOutcome(
                source=plan.source,
                items=(),
                duration_ms=0,
                status="skipped",
                error_type="AdapterNotConfigured",
            )
        try:
            result = await asyncio.wait_for(
                adapter.retrieve(plan, scope),
                timeout=plan.timeout_ms / 1000,
            )
            if not isinstance(result, tuple) or any(not isinstance(item, EvidenceItem) for item in result):
                raise TypeError("knowledge adapter must return tuple[EvidenceItem, ...]")
            authorized = tuple(masked for item in result if (masked := mask_evidence(item, scope)) is not None)
            return _SourceOutcome(
                source=plan.source,
                items=authorized,
                duration_ms=int((time.perf_counter() - started) * 1000),
                status="completed",
                scope_dropped=len(result) - len(authorized),
            )
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return _SourceOutcome(
                source=plan.source,
                items=(),
                duration_ms=int((time.perf_counter() - started) * 1000),
                status="skipped",
                error_type=type(exc).__name__,
            )


def _unique_queries(values: Sequence[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        query = str(value or "").strip()
        normalized = " ".join(query.lower().split())
        if not query or normalized in seen:
            continue
        seen.add(normalized)
        result.append(query)
    return tuple(result)


def _outcome_event(outcome: _SourceOutcome) -> ExecutionEvent:
    metadata = [
        EventMetadata(key="source", value=outcome.source),
        EventMetadata(key="result_count", value=str(len(outcome.items))),
    ]
    if outcome.error_type:
        metadata.append(EventMetadata(key="failure_reason", value=outcome.error_type))
    return ExecutionEvent(
        stage="knowledge",
        status="completed" if outcome.status == "completed" else "skipped",
        duration_ms=outcome.duration_ms,
        message=f"{outcome.source} retrieval {outcome.status}",
        metadata=tuple(metadata),
    )


async def discard_trace(event: ExecutionEvent) -> None:
    del event


__all__ = ["KnowledgeOrchestrator", "QueryRewriter", "TraceReporter", "discard_trace"]
