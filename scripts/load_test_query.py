from __future__ import annotations

import argparse
import json
import statistics
import threading
import time
from typing import Any

import httpx


def worker(
    *,
    base_url: str,
    token: str,
    rounds: int,
    question: str,
    timeout: float,
    out: list[dict[str, Any]],
    lock: threading.Lock,
    idx: int,
):
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    with httpx.Client(timeout=timeout) as client:
        for r in range(rounds):
            started = time.perf_counter()
            ok = False
            status = 0
            try:
                resp = client.post(
                    f"{base_url.rstrip('/')}/query",
                    json={
                        "question": question,
                        "use_web_fallback": True,
                        "use_reasoning": False,
                        "request_id": f"load-{idx}-{r}",
                    },
                    headers=headers,
                )
                status = int(resp.status_code)
                ok = 200 <= status < 300
            except Exception:
                status = -1
                ok = False
            elapsed_ms = (time.perf_counter() - started) * 1000.0
            with lock:
                out.append({"ok": ok, "status": status, "latency_ms": elapsed_ms})


def main():
    p = argparse.ArgumentParser(description="Simple concurrent load test for /query")
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--token", default="", help="Bearer token")
    p.add_argument("--concurrency", type=int, default=20)
    p.add_argument("--rounds", type=int, default=10)
    p.add_argument("--question", default="请总结本地知识库里关于安全基线的要点")
    p.add_argument("--timeout", type=float, default=30.0)
    args = p.parse_args()

    rows: list[dict[str, Any]] = []
    lock = threading.Lock()
    ts: list[threading.Thread] = []
    started = time.perf_counter()
    for i in range(max(1, args.concurrency)):
        t = threading.Thread(
            target=worker,
            kwargs={
                "base_url": args.base_url,
                "token": args.token,
                "rounds": max(1, args.rounds),
                "question": args.question,
                "timeout": float(args.timeout),
                "out": rows,
                "lock": lock,
                "idx": i,
            },
            daemon=True,
        )
        t.start()
        ts.append(t)
    for t in ts:
        t.join()
    total_s = max(0.0001, time.perf_counter() - started)
    latencies = [float(r["latency_ms"]) for r in rows]
    ok_rows = [r for r in rows if r.get("ok")]
    err_rows = [r for r in rows if not r.get("ok")]
    p95 = statistics.quantiles(latencies, n=100)[94] if len(latencies) >= 20 else (max(latencies) if latencies else 0.0)
    print(
        json.dumps(
            {
                "requests": len(rows),
                "ok": len(ok_rows),
                "errors": len(err_rows),
                "rps": round(len(rows) / total_s, 2),
                "avg_ms": round(statistics.mean(latencies), 2) if latencies else 0.0,
                "p95_ms": round(p95, 2),
                "status_counts": {k: sum(1 for r in rows if r.get("status") == k) for k in sorted({int(r.get("status", 0)) for r in rows})},
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
