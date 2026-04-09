import argparse
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load_queries(path: Path) -> list[str]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            q = line.strip()
            if q:
                rows.append(q)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="End-to-end query benchmark for latency and grounding quality.")
    parser.add_argument("--queries", default="data/eval/benchmark_queries.txt")
    parser.add_argument("--use-web", action="store_true")
    parser.add_argument("--no-reasoning", action="store_true")
    parser.add_argument("--strategy", default="")
    args = parser.parse_args()

    try:
        from app.graph.workflow import run_query
    except Exception as e:
        print(json.dumps({"ok": False, "error": f"runtime_unavailable:{type(e).__name__}"}, ensure_ascii=False, indent=2))
        return 1

    queries = _load_queries(Path(args.queries))
    if not queries:
        print(json.dumps({"ok": False, "error": "no_queries"}, ensure_ascii=False, indent=2))
        return 2

    latencies = []
    citation_counts = []
    support_ratios = []
    for q in queries:
        t0 = time.perf_counter()
        kwargs = {
            "use_web_fallback": args.use_web,
            "use_reasoning": not args.no_reasoning,
        }
        if str(args.strategy or "").strip():
            kwargs["retrieval_strategy"] = str(args.strategy).strip().lower()
        result = run_query(q, **kwargs)
        latencies.append((time.perf_counter() - t0) * 1000.0)
        vc = result.get("vector_result", {}).get("citations", []) or []
        wc = result.get("web_result", {}).get("citations", []) or []
        citation_counts.append(len(vc) + len(wc))
        support_ratios.append(float((result.get("grounding", {}) or {}).get("support_ratio", 0.0) or 0.0))

    out = {
        "ok": True,
        "num_queries": len(queries),
        "latency_ms": {
            "p50": statistics.median(latencies),
            "p95": sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)],
            "avg": statistics.mean(latencies),
        },
        "citations": {
            "avg": statistics.mean(citation_counts),
            "max": max(citation_counts),
        },
        "grounding_support_ratio": {
            "avg": statistics.mean(support_ratios),
            "min": min(support_ratios),
        },
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
