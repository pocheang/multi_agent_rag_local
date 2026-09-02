"""Wait for the backend's health endpoint, from inside its own container.

It used to take `--url` and hand it straight to `urlopen`, which is
`pythonsecurity:S8703`: a URL off the command line reaching an HTTP client is an
SSRF primitive, and `urlopen` speaks more than http -- `file:///etc/passwd`
returns a 200-shaped response and would have been reported as healthy.

Validating the string was the first attempt and did not settle it, correctly:
a check that returns its argument unchanged leaves the caller in control of the
host, which is the part that matters. So the host is no longer an argument. It
is a literal, the port is an integer, and the path is fixed -- there is no
value a caller can pass that makes this request go anywhere else.

Both call sites (deploy.sh, deploy.ps1) passed `http://127.0.0.1:8000/health`
and nothing else ever has, so the narrower interface loses nothing.
"""

from __future__ import annotations

import argparse
import time
import urllib.error
import urllib.request

# Not configurable, and that is the point: `exec -T backend` runs this inside the
# container it is checking.
HOST = "127.0.0.1"
PATH = "/health"


def wait_for_health(port: int, timeout: float, interval: float) -> bool:
    url = f"http://{HOST}:{port}{PATH}"
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
    parser = argparse.ArgumentParser(description="Wait for the QueryMind health endpoint on localhost")
    parser.add_argument("--port", type=int, default=8000, choices=range(1, 65536), metavar="PORT")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args(argv)

    target = f"http://{HOST}:{args.port}{PATH}"
    if wait_for_health(args.port, args.timeout, args.interval):
        print(f"Health check passed: {target}")
        return 0
    print(f"Health check timed out: {target}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
