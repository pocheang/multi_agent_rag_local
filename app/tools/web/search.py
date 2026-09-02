import logging
import threading

from ddgs import DDGS

from app.services.observability.log_safety import question_ref

logger = logging.getLogger(__name__)

# See `search_web`: concurrent DDGS construction wedges the process.
_CLIENT_LOCK = threading.Lock()


def _resolve_ddgs_eagerly() -> None:
    """Load ddgs's real implementation now, while one thread is running.

    `from ddgs import DDGS` does not import ddgs. The name is a proxy whose
    metaclass runs `importlib.import_module` on the first *call*, holding its own
    lock while it does -- and the module it imports calls `logging.getLogger` on
    the way in.

    One query can start several web searches, each in its own worker thread, so
    those are several concurrent first calls. The import lock and the logging
    lock get taken in opposite orders and the process wedges: verified on Windows
    with three worker threads inside `ddgs/__init__.py::_load_real`, one of them
    parked in `logging.getLogger`. What made it fatal rather than slow is that
    the stuck thread holds the logging lock, so every later log call blocks --
    including uvicorn's per-request access log. `/health` and `/openapi.json`
    stopped answering while the event loop itself was idle and healthy.

    Resolving it at import removes the race: by the time any request can arrive,
    the real module is loaded and `DDGS(...)` is an ordinary constructor. The
    `timeout` argument passed at the call site never helped -- it bounds the HTTP
    request, not the import.
    """

    try:
        DDGS.text  # noqa: B018 - attribute access is what triggers the proxy
    except Exception:  # pragma: no cover - must never break import
        logger.warning("ddgs could not be resolved at import; web search may be slow on first use")


_resolve_ddgs_eagerly()


def search_web(query: str, max_results: int = 5, timeout: int = 10) -> list[dict]:
    """
    Execute web search using DuckDuckGo.

    Args:
        query: Search query string
        max_results: Maximum number of results to return (default: 5)
        timeout: Timeout in seconds (default: 10)

    Returns:
        List of search results with title, href, and body

    Raises:
        Exception: If search fails or times out
    """
    results: list[dict] = []

    try:
        # Constructing a client is serialized; searching is not.
        #
        # `DDGS()` builds a `primp.Client` (a Rust HTTP client) which calls back
        # into Python logging on the way up. Two threads doing that at once
        # wedged the process: py-spy showed two workers parked in
        # `ddgs/http_client.py::__init__` at `logging.getLogger`, and the main
        # thread stuck in `Thread.start()`, with the whole server answering
        # nothing -- `/health` included -- at zero CPU.
        #
        # Resolving ddgs's lazy import at module load (below) was necessary and
        # not sufficient: the import race is one way in, and concurrent
        # construction is another. The cause lives inside a third-party Rust
        # client, so this holds the construction under one lock rather than
        # pretending to fix it there. The search itself runs outside the lock,
        # so several queries still overlap; only the constructor is one-at-a-time.
        with _CLIENT_LOCK:
            client = DDGS(timeout=timeout)
        with client as ddgs:
            for item in ddgs.text(query, max_results=max_results, region="wt-wt", safesearch="moderate"):
                results.append(
                    {
                        "title": item.get("title", ""),
                        "href": item.get("href", ""),
                        "body": item.get("body", ""),
                    }
                )
        logger.debug("Web search returned %d results for %s", len(results), question_ref(query))
    except Exception as e:
        logger.exception(f"Web search failed: {type(e).__name__}: {str(e)}")
        raise

    return results
