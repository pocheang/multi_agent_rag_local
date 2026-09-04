"""Measure retrieval quality on a corpus that ships with the repository.

Why this exists at all: CLAUDE.md has claimed P@5 > 0.85 for a long time and
nothing measured it. `POST /api/evaluation/run` reads `data/evaluation/*.json`,
and `data/` is gitignored -- so on every checkout where nobody hand-placed a file
the endpoint returned 404. A target with no measurement behind it is a number,
not a claim.

Two decisions worth knowing before changing this module.

**It runs through `KnowledgeOrchestrator`, not through the evaluation
baselines.** The baselines in `app/evaluation/baselines/api_retriever.py` call
`similarity_search` and `hybrid_search_with_diagnostics` directly: they never
touch the orchestrator, the adapters, or `reciprocal_rank_fuse`, so they cannot
observe a change to any of them. Going through the orchestrator costs one more
import and measures the path the chat request actually takes -- including
`_flatten`, RRF, deduplication and `mask_evidence`.

**BM25 only, so it needs no model.** `read_corpus_records` reads a plain JSONL
file at `corpus_store_path`; nothing here needs an embedding model, Chroma,
Neo4j or an LLM, which is what lets it run in CI and on a fresh checkout. The
vector and hybrid paths deliberately stay manual: `_load_cross_encoder` is built
with `local_files_only=True`, so a CI run without the model downloaded would
silently fall back to `lexical_rerank` and publish a number measuring the
fallback rather than the reranker. A green metric measuring the wrong thing is
worse than no metric.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from app.domain.knowledge import AccessScope, KnowledgeSourcePlan, KnowledgeStrategy
from app.evaluation.models import TestQuery
from app.knowledge.orchestrator import KnowledgeOrchestrator
from app.services.security.access_scope import DEFAULT_CONTEXT_FIELDS

# Deployment-specific override first, then the set that ships with the repo --
# the same order and the same reason as `_BENCHMARK_QUERY_PATHS` in
# app/services/runtime/runtime_ops.py. Only the tracked default makes this
# runnable on a fresh checkout.
CORPUS_PATHS = (
    Path("data/eval/retrieval_corpus.jsonl"),
    Path("config/eval/retrieval_corpus.jsonl"),
)
QUERY_PATHS = (
    Path("data/eval/retrieval_queries.json"),
    Path("config/eval/retrieval_queries.json"),
)

EVAL_TENANT = "eval-tenant"
EVAL_USER = "eval-user"


def resolve(paths: tuple[Path, ...]) -> Path:
    """First existing path wins; a genuinely missing set is an error, not a zero."""

    for candidate in paths:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"no retrieval evaluation file found at any of: {', '.join(str(p) for p in paths)}")


def load_corpus_sources(path: Path | None = None) -> tuple[str, ...]:
    target = path or resolve(CORPUS_PATHS)
    sources: list[str] = []
    for line in target.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        source = str((json.loads(line).get("metadata") or {}).get("source", "") or "")
        if source:
            sources.append(source)
    return tuple(dict.fromkeys(sources))


def load_queries(path: Path | None = None) -> tuple[TestQuery, ...]:
    target = path or resolve(QUERY_PATHS)
    payload = json.loads(target.read_text(encoding="utf-8"))
    return tuple(TestQuery(**row) for row in payload.get("queries", []))


def eval_scope(sources: tuple[str, ...]) -> AccessScope:
    """The scope the corpus rows declare.

    `mask_evidence` runs inside `_retrieve_source`, so the rows' `tenant_id`,
    `owner_user_id` and `visibility` have to match what is asked for here. When
    they do not, every item is dropped and the metric reads 0.00 for a reason
    that has nothing to do with retrieval -- which is why
    `test_a_mismatched_scope_returns_nothing` exists.
    """

    return AccessScope(
        tenant_id=EVAL_TENANT,
        user_id=EVAL_USER,
        role="viewer",
        allowed_sources=frozenset(sources),
        allowed_fields=DEFAULT_CONTEXT_FIELDS,
    )


@dataclass(frozen=True)
class RetrievalScore:
    """Per-query outcome plus the aggregates, so a failure can name the query.

    **`precision_at_5` here is capped at 0.2 and that is not a bad score.** Every
    query in the shipped set has exactly one relevant document, so at most one of
    five retrieved items can be relevant. It is reported because it is cheap, but
    `mrr` is the metric with headroom on this corpus, and neither number is
    comparable to a P@5 target quoted for a corpus with several relevant
    documents per query. Comparing them is the mistake this docstring exists to
    prevent.
    """

    ranks: dict[str, int]  # query id -> 1-based rank of the gold source, 0 if absent
    precision_at_5: float
    mrr: float

    @property
    def reciprocal_ranks(self) -> dict[str, float]:
        return {query_id: (1.0 / rank if rank else 0.0) for query_id, rank in self.ranks.items()}


async def measure(
    queries: tuple[TestQuery, ...],
    scope: AccessScope,
    *,
    top_k: int = 5,
) -> RetrievalScore:
    """Run each query through the real orchestrator with a BM25-only strategy."""

    async def _discard(_event: object) -> None:
        return None

    orchestrator = KnowledgeOrchestrator()
    ranks: dict[str, int] = {}
    hits_at_5 = 0.0
    for query in queries:
        strategy = KnowledgeStrategy(
            sources=(
                KnowledgeSourcePlan(
                    source="bm25",
                    queries=(query.query,),
                    top_k=top_k,
                    timeout_ms=10_000,
                ),
            ),
            # Both off so the measurement is of retrieval, not of the rewriter or
            # the reranker -- the reranker in particular would degrade to a
            # lexical fallback without its model and quietly measure that.
            rewrite=False,
            rerank=False,
            rationale="offline retrieval evaluation",
        )
        context = await orchestrator.retrieve(strategy, scope, _discard)
        retrieved = [item.source for item in context.evidence][:top_k]
        gold = set(query.expected_docs)
        ranks[query.id] = next((index for index, source in enumerate(retrieved, start=1) if source in gold), 0)
        hits_at_5 += len([source for source in retrieved if source in gold]) / top_k

    total = max(1, len(queries))
    return RetrievalScore(
        ranks=ranks,
        precision_at_5=hits_at_5 / total,
        mrr=sum(1.0 / rank for rank in ranks.values() if rank) / total,
    )


__all__ = [
    "CORPUS_PATHS",
    "EVAL_TENANT",
    "EVAL_USER",
    "QUERY_PATHS",
    "RetrievalScore",
    "eval_scope",
    "load_corpus_sources",
    "load_queries",
    "measure",
    "resolve",
]
