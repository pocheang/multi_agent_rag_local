from __future__ import annotations

import argparse
import time
import urllib.error
import urllib.request


def wait_for_url(url: str, timeout: float, interval: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=min(10.0, max(interval, 1.0))) as response:
                if 200 <= response.status < 400:
                    return True
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(interval)
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Wait for a QueryMind HTTP health endpoint")
    parser.add_argument("--url", required=True)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args(argv)
    if wait_for_url(args.url, args.timeout, args.interval):
        print(f"Health check passed: {args.url}")
        return 0
    print(f"Health check timed out: {args.url}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
