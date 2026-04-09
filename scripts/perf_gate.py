from __future__ import annotations

import argparse
import json
import subprocess
import sys


def main():
    p = argparse.ArgumentParser(description="Performance gate runner")
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    p.add_argument("--token", default="")
    p.add_argument("--concurrency", type=int, default=20)
    p.add_argument("--rounds", type=int, default=8)
    p.add_argument("--max-p95-ms", type=float, default=4000.0)
    p.add_argument("--max-error-rate", type=float, default=5.0, help="percent")
    args = p.parse_args()

    cmd = [
        sys.executable,
        "scripts/load_test_query.py",
        "--base-url",
        args.base_url,
        "--token",
        args.token,
        "--concurrency",
        str(args.concurrency),
        "--rounds",
        str(args.rounds),
    ]
    out = subprocess.check_output(cmd, text=True)
    last = out.strip().splitlines()[-1]
    data = json.loads(last)
    req = max(1, int(data.get("requests", 1)))
    err = int(data.get("errors", 0))
    p95 = float(data.get("p95_ms", 0.0))
    err_rate = (err / req) * 100.0
    ok = (p95 <= args.max_p95_ms) and (err_rate <= args.max_error_rate)
    result = {
        "ok": ok,
        "p95_ms": p95,
        "error_rate_percent": round(err_rate, 3),
        "thresholds": {
            "max_p95_ms": args.max_p95_ms,
            "max_error_rate_percent": args.max_error_rate,
        },
        "raw": data,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not ok:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
