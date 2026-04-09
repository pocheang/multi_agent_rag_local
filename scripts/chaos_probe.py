from __future__ import annotations

import argparse
import json
import time

import httpx


def main():
    p = argparse.ArgumentParser(description="Chaos smoke probe: check readiness and query degradation behavior")
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--token", default="")
    p.add_argument("--attempts", type=int, default=5)
    p.add_argument("--sleep-seconds", type=float, default=1.0)
    args = p.parse_args()

    headers = {"Authorization": f"Bearer {args.token}"} if args.token else {}
    base = args.base_url.rstrip("/")
    out = {"ready": None, "runs": []}
    with httpx.Client(timeout=20.0) as client:
        try:
            ready = client.get(f"{base}/ready")
            out["ready"] = {"status": ready.status_code, "body": ready.json()}
        except Exception as e:
            out["ready"] = {"status": -1, "error": str(e)}

        for i in range(max(1, args.attempts)):
            started = time.perf_counter()
            try:
                resp = client.post(
                    f"{base}/query",
                    headers=headers,
                    json={
                        "question": "现在系统负载高时会如何降级？",
                        "use_web_fallback": True,
                        "use_reasoning": True,
                        "request_id": f"chaos-{i}",
                    },
                )
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                out["runs"].append(
                    {
                        "idx": i,
                        "status": int(resp.status_code),
                        "latency_ms": round(elapsed_ms, 2),
                        "route": body.get("route"),
                        "debug": body.get("debug", {}),
                    }
                )
            except Exception as e:
                elapsed_ms = (time.perf_counter() - started) * 1000.0
                out["runs"].append({"idx": i, "status": -1, "latency_ms": round(elapsed_ms, 2), "error": str(e)})
            time.sleep(max(0.0, float(args.sleep_seconds)))

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
