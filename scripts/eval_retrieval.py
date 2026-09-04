"""Print retrieval quality over the evaluation corpus.

    python scripts/eval_retrieval.py            # BM25, no model needed
    python scripts/eval_retrieval.py --vector   # adds vector + hybrid, needs BGE-M3

The BM25 form is the one `tests/evaluation/test_retrieval_metric.py` asserts on,
and it runs anywhere: `read_corpus_records` reads a plain JSONL file, so there is
no embedding model, no Chroma, no Neo4j and no LLM involved.

`--vector` is deliberately **not** in CI. `_load_cross_encoder` is built with
`local_files_only=True`, so on a machine without the reranker downloaded it
returns None and retrieval silently degrades to `lexical_rerank` -- a CI job
would publish a number measuring the lexical fallback rather than the reranker,
which is worse than publishing nothing. It also needs a populated (gitignored)
Chroma directory. Same reasoning as `npm run screenshots`: a local before/after
tool, not a gate.

Point it at your own corpus by placing `data/eval/retrieval_corpus.jsonl` and
`data/eval/retrieval_queries.json`; those win over the tracked defaults.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# The query set is bilingual and a Windows console defaults to cp1252, where
# printing a Chinese question raises UnicodeEncodeError and the run dies after
# the measurement but before the numbers.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):  # pragma: no cover - non-reconfigurable stream
        pass


async def _run(use_vector: bool) -> int:
    from app.core.config import get_settings
    from app.evaluation.retrieval_eval import (
        CORPUS_PATHS,
        QUERY_PATHS,
        eval_scope,
        load_corpus_sources,
        load_queries,
        measure,
        resolve,
    )
    from app.retrievers.bm25_retriever import reset_bm25_cache

    corpus = resolve(CORPUS_PATHS)
    queries_path = resolve(QUERY_PATHS)

    os.environ["CORPUS_STORE_PATH"] = str(corpus)
    get_settings.cache_clear()
    reset_bm25_cache()

    queries = load_queries(queries_path)
    sources = load_corpus_sources(corpus)
    score = await measure(queries, eval_scope(sources))

    print(f"corpus : {corpus} ({len(sources)} sources)")
    print(f"queries: {queries_path} ({len(queries)} queries)")
    print()
    print(f"{'query':<8} {'rank':>4}  question")
    for query in queries:
        rank = score.ranks.get(query.id, 0)
        print(f"{query.id:<8} {rank if rank else '-':>4}  {query.query}")
    print()
    print(f"MRR  : {score.mrr:.4f}")
    print(f"P@5  : {score.precision_at_5:.4f}")

    if use_vector:
        print()
        print("--vector is not implemented here yet: it needs a populated Chroma")
        print("directory and a downloaded BGE-M3, neither of which this script builds.")
        print("Ingest a corpus first, then use POST /api/evaluation/run.")

    return 0 if score.mrr == 1.0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vector", action="store_true", help="also report the vector/hybrid baselines")
    args = parser.parse_args()
    return asyncio.run(_run(args.vector))


if __name__ == "__main__":
    raise SystemExit(main())
