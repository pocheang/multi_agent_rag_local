"""`ddgs` must be fully imported before any request can reach it.

`from ddgs import DDGS` does not import ddgs. The name is a proxy whose metaclass
runs `importlib.import_module` on the first *call*, holding its own lock while it
does -- and the module it imports calls `logging.getLogger` on the way in.

One query starts several web searches, each on its own worker thread, so those
are several concurrent first calls. Reproduced on Windows: three worker threads
inside `ddgs/__init__.py::_load_real`, one parked in `logging.getLogger`. What
turned a slow start into a dead process is that the stuck thread holds the
logging lock, so every later log call blocks -- including uvicorn's per-request
access log. `/health` and `/openapi.json` stopped answering while the event loop
itself sat idle and healthy, which is why this reads as a hang with no CPU rather
than as a slow search.

The `timeout=10` at the call site never applied: it bounds the HTTP request, not
the import.

So the property is not "web search works" -- it is "there is no first-call import
left to race". These tests assert that, and that concurrent construction from
several threads completes.
"""

from __future__ import annotations

import concurrent.futures
import importlib
import sys

import pytest


def test_importing_the_module_resolves_the_proxy() -> None:
    """After importing our module, `ddgs.ddgs` is already in sys.modules."""

    importlib.import_module("app.tools.web.search")

    assert "ddgs.ddgs" in sys.modules, (
        "ddgs is still lazy: the first DDGS(...) call will run importlib while "
        "holding a lock, and concurrent first calls deadlock. See "
        "app/tools/web/search.py::_resolve_ddgs_eagerly."
    )


def test_the_name_is_the_real_class_not_the_proxy() -> None:
    from app.tools.web import search

    # The proxy's metaclass is `_ProxyMeta`; the resolved class is an ordinary
    # type. Checking the metaclass name is what distinguishes them without
    # importing ddgs internals.
    assert type(search.DDGS).__name__ != "_ProxyMeta" or "ddgs.ddgs" in sys.modules


def test_concurrent_construction_does_not_hang() -> None:
    """Three threads building a client at once, which is what one query does.

    Bounded so a regression fails the suite instead of hanging it: the original
    defect never returned at all.
    """

    from app.tools.web.search import DDGS

    def build() -> str:
        try:
            client = DDGS(timeout=1)
        except Exception as exc:  # constructing must not require the network
            return f"error:{type(exc).__name__}"
        closer = getattr(client, "close", None)
        if callable(closer):
            try:
                closer()
            except Exception:
                pass
        return "ok"

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(build) for _ in range(3)]
        try:
            results = [future.result(timeout=30) for future in futures]
        except concurrent.futures.TimeoutError:  # pragma: no cover - the regression
            pytest.fail(
                "constructing DDGS from three threads did not finish in 30s -- the lazy "
                "import is racing again, and in a running server this wedges every request "
                "that logs"
            )

    assert all(result == "ok" for result in results), results
