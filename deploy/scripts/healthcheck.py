from __future__ import annotations

import argparse
import time
import urllib.error
import urllib.parse
import urllib.request


def _checked(url: str) -> str:
    """Only http and https. `urlopen` speaks more than that.

    `file:///etc/passwd` is a URL `urlopen` will happily open and report as
    healthy, which is not a scheme any health endpoint uses and not a thing a
    deploy script should be able to be pointed at -- `pythonsecurity:S8703`.
    A host allow-list would be wrong here: the whole point is to wait on
    whatever host is being deployed to.
    """

    scheme = urllib.parse.urlparse(url).scheme.lower()
    if scheme not in {"http", "https"}:
        raise ValueError(f"--url must be http or https, not {scheme or 'a relative path'}")
    return url


def wait_for_url(url: str, timeout: float, interval: float) -> bool:
    url = _checked(url)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=min(10.0, max(interval, 1.0))) as response:  # noqa: S310
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
    try:
        if wait_for_url(args.url, args.timeout, args.interval):
            print(f"Health check passed: {args.url}")
            return 0
    except ValueError as exc:
        print(f"Health check error: {exc}")
        return 2
    print(f"Health check timed out: {args.url}")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
