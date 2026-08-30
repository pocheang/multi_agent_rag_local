import logging

from ddgs import DDGS

from app.services.observability.log_safety import question_ref

logger = logging.getLogger(__name__)


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
        with DDGS(timeout=timeout) as ddgs:
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
        logger.error(f"Web search failed: {type(e).__name__}: {str(e)}")
        raise

    return results
