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
from app.knowledge.adapters import KnowledgeAdapter, build_default_adapters, flatten_ranked_groups
from app.knowledge.context import ContextBuilder
from app.knowledge.deduplication import deduplicate_evidence
from app.knowledge.fusion import reciprocal_rank_fuse, rerank_evidence
from app.knowledge.queries import unique_queries as _unique_queries
from app.privacy.dlp import mask_evidence
from app.services.query.rule_rewrite import build_rewrite_queries

TraceReporter = Callable[[ExecutionEvent], Awaitable[None]]
QueryRewriter = Callable[[str, Sequence[object]], Sequence[str]]


@dataclass(frozen=True)
class _SourceOutcome:
    source: KnowledgeSource
    # `groups` is one ranked list per query in the plan; `items` is those lists
    # flattened, which is what counts, diagnostics and prior evidence read. Only
    # fusion needs them apart -- see the note at the reciprocal_rank_fuse call.
    items: tuple[EvidenceItem, ...]
    duration_ms: int
    status: str
    error_type: str | None = None
    scope_dropped: int = 0
    groups: tuple[tuple[EvidenceItem, ...], ...] = ()


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
        self._retrieval_budget_ms = active.stage_timeout_retrieval_ms
        self._context_builder = ContextBuilder(token_budget=active.knowledge_context_token_budget)
        self._rewrite = rewriter or (
            lambda query, conversation: build_rewrite_queries(
                query,
                enable_llm=bool(active.query_rewrite_enabled and active.query_rewrite_with_llm),
                enable_decompose=False,
                max_variants=active.query_rewrite_max_variants,
                conversation=conversation,
            )
        )

    async def retrieve(
        self,
        strategy: KnowledgeStrategy,
        scope: AccessScope,
        trace: TraceReporter,
        conversation: Sequence[object] = (),
    ) -> ContextBundle:
        """Execute only selected sources with bounded timeouts and explicit diagnostics.

        `conversation` reaches only the rewrite step, and only to complete a
        follow-up question into a standalone one. It is empty when the caller
        turned context tracking off, and empty is the safe value: retrieval then
        runs on the question exactly as asked.
        """

        started = time.perf_counter()
        rewritten, rewrite_diagnostics = await self._rewrite_once(strategy, conversation)
        source_plans = tuple(self._with_queries(plan, rewritten) for plan in strategy.sources)
        outcomes, phase_diagnostics = await self._retrieve_in_phases(source_plans, scope, started)
        trace_failures = 0
        for outcome in outcomes:
            try:
                await trace(_outcome_event(outcome))
            except asyncio.CancelledError:
                raise
            except Exception:
                trace_failures += 1

        # One ranked list per (source, query), not per source. RRF scores by
        # position, so folding a source's queries into one list charges the
        # second query's best hit a rank it did not earn: it lands after the
        # first query's whole list. Interleaving them (which `_flatten` still
        # does for the flat view) softens that but does not remove it -- only
        # keeping the lists apart gives every query's rank-1 the same 1/(k+1).
        #
        # It also makes agreement mean what it should: a document two queries
        # both rank first now accumulates two full contributions.
        ranked_lists = tuple(group for outcome in outcomes if outcome.status == "completed" for group in outcome.groups)
        fused = reciprocal_rank_fuse(ranked_lists, rrf_k=self._rrf_k)
        deduplicated = deduplicate_evidence(fused)
        primary_query = strategy.sources[0].queries[0]
        # The Knowledge Agent sizes the answer set together with the search that
        # produces it; the setting is the default when it has no opinion.
        rerank_top_n = strategy.rerank_top_n or self._reranker_top_n
        if strategy.rerank:
            reranked, reranker_diagnostics = await rerank_evidence(
                primary_query,
                deduplicated,
                top_n=rerank_top_n,
                timeout_ms=self._reranker_timeout_ms,
                enabled=self._reranker_enabled,
            )
        else:
            reranked = deduplicated[:rerank_top_n]
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
            **phase_diagnostics,
            "selected_sources": tuple(plan.source for plan in source_plans),
            "adapter_count": len(source_plans),
            "source_status": {outcome.source: outcome.status for outcome in outcomes},
            # Why a source did not complete, not just that it did not. A source
            # skipped because the caller has no documents was never attempted;
            # collapsing that into "failed" is what turned a new user's first
            # question into a 500.
            "source_error_type": {outcome.source: outcome.error_type for outcome in outcomes if outcome.error_type},
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
            "rerank_top_n": rerank_top_n,
            "post_rerank_count": len(reranked),
            "knowledge_duration_ms": int((time.perf_counter() - started) * 1000),
        }
        return self._context_builder.build(reranked, scope, diagnostics=diagnostics)

    async def _retrieve_in_phases(
        self,
        source_plans: tuple[KnowledgeSourcePlan, ...],
        scope: AccessScope,
        started: float,
    ) -> tuple[tuple[_SourceOutcome, ...], dict[str, object]]:
        """Run independent sources concurrently, then any that read their results.

        Concurrency is the default because sources are independent. A source that
        declares otherwise (`PriorEvidenceAdapter.wants_prior_evidence`) gets a
        second phase, and pays for it: its duration lands on the critical path
        instead of overlapping the others. So the second phase exists only when an
        adapter says it would use it -- with `GRAPH_RAG_ENHANCED` off, everything
        is still one `gather` and retrieval latency is unchanged.

        Phase two inherits what is *left* of the retrieval stage rather than a
        fresh copy of each plan's timeout. Otherwise two phases could take
        `phase_one + phase_two` and blow through `STAGE_TIMEOUT_RETRIEVAL_MS`,
        turning a sharper graph lookup into a degraded stage -- a strictly worse
        trade than the plain lookup it replaced.

        Order is restored by *index*, not by source name: `sources` carries no
        uniqueness constraint, so keying the reassembly on the source would quietly
        collapse two plans for one source into one outcome. Downstream,
        `zip(source_plans, outcomes, strict=True)` pairs a plan with its outcome by
        position.
        """
        deferred = tuple(index for index, plan in enumerate(source_plans) if self._wants_prior_evidence(plan))
        if not deferred:
            outcomes = await asyncio.gather(*(self._retrieve_source(plan, scope) for plan in source_plans))
            return tuple(outcomes), {"retrieval_phases": 1, "deferred_sources": ()}

        first = tuple(index for index in range(len(source_plans)) if index not in set(deferred))
        first_outcomes = await asyncio.gather(*(self._retrieve_source(source_plans[i], scope) for i in first))
        prior = _flatten_items(first_outcomes)
        elapsed_ms = int((time.perf_counter() - started) * 1000)
        second_outcomes = await asyncio.gather(
            *(
                self._retrieve_source(
                    self._within_remaining_budget(source_plans[i], elapsed_ms),
                    scope,
                    prior=prior,
                )
                for i in deferred
            )
        )
        by_index = dict(zip(first, first_outcomes, strict=True)) | dict(zip(deferred, second_outcomes, strict=True))
        ordered = tuple(by_index[index] for index in range(len(source_plans)))
        return ordered, {
            "retrieval_phases": 2,
            "deferred_sources": tuple(source_plans[i].source for i in deferred),
            "phase_one_duration_ms": elapsed_ms,
        }

    def _wants_prior_evidence(self, plan: KnowledgeSourcePlan) -> bool:
        adapter = self._adapters.get(plan.source)
        wants = getattr(adapter, "wants_prior_evidence", None)
        if wants is None:
            return False
        try:
            return bool(wants())
        except Exception:
            # An adapter that cannot decide gets the concurrent path: the phased
            # one is the optimization, so failing into it would trade latency for
            # nothing.
            return False

    def _within_remaining_budget(self, plan: KnowledgeSourcePlan, elapsed_ms: int) -> KnowledgeSourcePlan:
        remaining = self._retrieval_budget_ms - elapsed_ms
        if remaining >= plan.timeout_ms:
            return plan
        # The contract floors timeout_ms at 100; a smaller remainder means phase one
        # already spent the stage, and the floor keeps the plan constructible. The
        # stage ceiling above still bounds the whole thing.
        return plan.model_copy(update={"timeout_ms": max(100, remaining)})

    async def _rewrite_once(
        self,
        strategy: KnowledgeStrategy,
        conversation: Sequence[object] = (),
    ) -> tuple[tuple[str, ...], dict[str, object]]:
        primary = strategy.sources[0].queries[0]
        if not strategy.rewrite:
            return (primary,), {
                "rewrite_invocations": 0,
                "rewrite_backend": "disabled",
                "rewrite_fallback_reason": None,
                "rewritten_queries": (primary,),
            }
        try:
            values = await asyncio.to_thread(self._rewrite, primary, conversation)
            rewritten = _unique_queries(values) or (primary,)
            return rewritten, {
                "rewrite_invocations": 1,
                "rewrite_backend": "configured",
                "rewrite_fallback_reason": None,
                "rewritten_queries": rewritten,
                "rewrite_context_turns": len(tuple(conversation)),
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

    async def _retrieve_source(
        self,
        plan: KnowledgeSourcePlan,
        scope: AccessScope,
        prior: tuple[EvidenceItem, ...] = (),
    ) -> _SourceOutcome:
        started = time.perf_counter()
        adapter = self._adapters.get(plan.source)
        if plan.source in {"vector", "bm25", "graph", "wiki", "multimodal"} and not (
            scope.document_ids or scope.allowed_sources
        ):
            # Not a failure: this caller has no documents, so there is nothing
            # for a document-backed source to search. `EmptyAccessScope` is the
            # name downstream checks for -- see `NOT_ATTEMPTED` in
            # app/agents/rag/service.py.
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
            retrieve = (
                adapter.retrieve_with_prior(plan, scope, prior)
                if prior and hasattr(adapter, "retrieve_with_prior")
                else adapter.retrieve(plan, scope)
            )
            result = await asyncio.wait_for(retrieve, timeout=plan.timeout_ms / 1000)
            if not isinstance(result, tuple) or any(
                not isinstance(group, tuple) or any(not isinstance(item, EvidenceItem) for item in group)
                for group in result
            ):
                raise TypeError("knowledge adapter must return one ranked tuple[EvidenceItem, ...] per query")
            # Masked per group so the ranks survive it: dropping an unauthorized
            # item must close the gap within its own list, not merge the lists.
            groups = tuple(
                tuple(masked for item in group if (masked := mask_evidence(item, scope)) is not None)
                for group in result
            )
            retrieved = sum(len(group) for group in result)
            authorized = flatten_ranked_groups(groups)
            return _SourceOutcome(
                source=plan.source,
                items=authorized,
                duration_ms=int((time.perf_counter() - started) * 1000),
                status="completed",
                scope_dropped=retrieved - len(authorized),
                groups=groups,
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


def _flatten_items(outcomes: Sequence[_SourceOutcome]) -> tuple[EvidenceItem, ...]:
    """Only completed sources: a timed-out source has no results, not zero results."""
    return tuple(item for outcome in outcomes if outcome.status == "completed" for item in outcome.items)


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
