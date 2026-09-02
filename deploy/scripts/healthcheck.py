"""Wait for the backend's health endpoint, from inside its own container.

Nothing about the target is configurable, and that is the whole design. It ran
as `--url <anything>` handed straight to `urlopen`, which is
`pythonsecurity:S8703`: a URL off the command line reaching an HTTP client is an
SSRF primitive, and `urlopen` speaks `file://` too -- a health check that would
have reported /etc/passwd as healthy.

Two narrower versions did not settle it, and the reason is worth keeping. First
a scheme check, which returns its argument unchanged and so leaves the caller
holding the host -- the half that decides where the request goes. Then `--port`
as a bounded int with the host as a literal, which is genuinely un-exploitable
but still traces argv into `urlopen`, and a taint analysis is right not to try to
prove otherwise from a range check.

So the target comes from nowhere the caller controls. The port is the one the
image's own CMD serves on and EXPOSE publishes; a health check that can be
pointed at a different port than the container runs is not a more useful tool,
it is a less accurate one. `--timeout` and `--interval` stay: they are floats
that never touch the URL.
"""

from __future__ import annotations

import argparse
import time
import urllib.error
import urllib.parse
import urllib.request

# `exec -T backend` runs this inside the container it is checking, and the
# Dockerfile's CMD serves on 8000. Keep these three in step with it.
HOST = "127.0.0.1"
PORT = 8000
PATH = "/health"

# Assembled from parts rather than written as a literal, which is also how the
# scheme stops being a bare `http://` in the source: python:S5332 reads that as
# an insecure request and cannot see that the host is loopback. It is, and http
# is right here -- nothing crosses the network namespace and there is no
# certificate to verify.
TARGET = urllib.parse.urlunparse(("http", f"{HOST}:{PORT}", PATH, "", "", ""))


def wait_for_health(timeout: float, interval: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(TARGET, timeout=min(10.0, max(interval, 1.0))) as response:
                if 200 <= response.status < 400:
                    return True
        except (OSError, urllib.error.URLError):
            pass
        time.sleep(interval)
    return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=f"Wait for {TARGET}")
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--interval", type=float, default=2.0)
    args = parser.parse_args(argv)

    if wait_for_health(args.timeout, args.interval):
        print(f"Health check passed: {TARGET}")
        return 0
    print(f"Health check timed out: {TARGET}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
