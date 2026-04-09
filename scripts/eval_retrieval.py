import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_cases(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
    return rows


def _hit_case(result: list[dict], must_contain: list[str]) -> bool:
    if not must_contain:
        return bool(result)
    text_pool = "\n".join([str(x.get("text", "")) for x in result]).lower()
    return all(str(x).lower() in text_pool for x in must_contain)


def evaluate(cases: list[dict[str, Any]], retrieval_strategy: str | None = None) -> dict[str, Any]:
    try:
        from app.retrievers.hybrid_retriever import hybrid_search_with_diagnostics
    except Exception as e:
        return {
            "total": len(cases),
            "hit": 0,
            "recall_at_k": 0.0,
            "error": f"retrieval_runtime_unavailable:{type(e).__name__}",
        }
    total = len(cases)
    if total == 0:
        return {"total": 0, "hit": 0, "recall_at_k": 0.0}
    hit = 0
    for c in cases:
        query = str(c.get("query", ""))
        must_contain = c.get("must_contain", []) or []
        allowed_sources = c.get("allowed_sources")
        result, _diag = hybrid_search_with_diagnostics(
            query,
            allowed_sources=allowed_sources,
            retrieval_strategy=retrieval_strategy,
        )
        if _hit_case(result, must_contain):
            hit += 1
    return {"total": total, "hit": hit, "recall_at_k": hit / total}


def autotune(cases: list[dict[str, Any]], retrieval_strategy: str | None = None) -> dict[str, Any]:
    try:
        from app.core.config import get_settings
        from app.retrievers.hybrid_retriever import hybrid_search_with_diagnostics  # noqa: F401
    except Exception as e:
        return {"score": 0.0, "params": None, "metrics": {"error": f"retrieval_runtime_unavailable:{type(e).__name__}"}}
    settings = get_settings()
    original = {
        "hybrid_vector_weight": settings.hybrid_vector_weight,
        "hybrid_bm25_weight": settings.hybrid_bm25_weight,
        "vector_similarity_threshold": settings.vector_similarity_threshold,
        "vector_similarity_relaxed_threshold": settings.vector_similarity_relaxed_threshold,
        "reranker_top_n": settings.reranker_top_n,
    }
    candidates = [
        {"hybrid_vector_weight": 0.95, "hybrid_bm25_weight": 0.05, "vector_similarity_threshold": 0.2, "vector_similarity_relaxed_threshold": 0.05, "reranker_top_n": 5},
        {"hybrid_vector_weight": 0.9, "hybrid_bm25_weight": 0.1, "vector_similarity_threshold": 0.18, "vector_similarity_relaxed_threshold": 0.05, "reranker_top_n": 6},
        {"hybrid_vector_weight": 0.85, "hybrid_bm25_weight": 0.15, "vector_similarity_threshold": 0.15, "vector_similarity_relaxed_threshold": 0.03, "reranker_top_n": 7},
    ]

    best = {"score": -1.0, "params": None, "metrics": None}
    for cand in candidates:
        for k, v in cand.items():
            setattr(settings, k, v)
        metrics = evaluate(cases, retrieval_strategy=retrieval_strategy)
        score = float(metrics.get("recall_at_k", 0.0))
        if score > best["score"]:
            best = {"score": score, "params": dict(cand), "metrics": metrics}

    for k, v in original.items():
        setattr(settings, k, v)
    return best


def main():
    parser = argparse.ArgumentParser(description="Offline retrieval evaluation and lightweight auto-tuning.")
    parser.add_argument("--dataset", default="data/eval/retrieval_eval.jsonl")
    parser.add_argument("--autotune", action="store_true")
    parser.add_argument("--strategy", default="")
    args = parser.parse_args()

    cases = _load_cases(Path(args.dataset))
    strategy = str(args.strategy or "").strip().lower() or None
    if args.autotune:
        best = autotune(cases, retrieval_strategy=strategy)
        print(json.dumps(best, ensure_ascii=False, indent=2))
        return
    print(json.dumps(evaluate(cases, retrieval_strategy=strategy), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
