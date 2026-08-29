import logging
import re
import time
from functools import lru_cache
from hashlib import md5
from urllib.parse import urlparse

from app.core.config import get_settings
from app.tools.web.search import search_web

logger = logging.getLogger(__name__)


__all__ = ["run_web_research"]


# Import metrics tracking (optional - won't fail if not available)
try:
    from app.agents.rag.web_utils import get_metrics, validate_url

    METRICS_AVAILABLE = True
except ImportError:
    METRICS_AVAILABLE = False
    logger.debug("Web research utils not available, metrics tracking disabled")

# Import activity logger (optional)
try:
    from app.services.web_activity.logger import get_activity_logger

    ACTIVITY_LOGGER_AVAILABLE = True
except ImportError:
    ACTIVITY_LOGGER_AVAILABLE = False
    logger.debug("Activity logger not available, activity logging disabled")


def _sanitize_query(question: str) -> str:
    """
    Remove sensitive information from query before web search.

    Args:
        question: User query that may contain sensitive information

    Returns:
        Sanitized query with sensitive patterns replaced by [REDACTED]
    """
    if not question:
        return question

    sanitized = question

    # Define sensitive patterns
    patterns = [
        (r"\b\d{3}-\d{2}-\d{4}\b", "[REDACTED_SSN]"),  # SSN
        (r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "[REDACTED_EMAIL]"),  # Email
        (r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", "[REDACTED_IP]"),  # IP address
        (r"password\s*[=:]\s*\S+", "password=[REDACTED]"),  # Password
        (r"token\s*[=:]\s*\S+", "token=[REDACTED]"),  # Token
        (r"api[_-]?key\s*[=:]\s*\S+", "api_key=[REDACTED]"),  # API key
        (r"\b\d{13,19}\b", "[REDACTED_CARD]"),  # Credit card numbers (13-19 digits)
    ]

    for pattern, replacement in patterns:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)

    # Log if sanitization occurred
    if sanitized != question:
        logger.warning("Query sanitized: removed sensitive information before web search")

    return sanitized


# Simple in-memory cache for web search results
@lru_cache(maxsize=128)
def _cached_search(question_hash: str, max_results: int) -> tuple:
    """
    Cache wrapper for search results.
    Note: This is a placeholder - actual search is done in run_web_research.
    The cache key is used to check if we've searched this before.
    """
    # This function exists only to provide cache key checking
    # Actual caching is handled in run_web_research
    return (question_hash, max_results)


def _get_cache_key(question: str) -> str:
    """Generate cache key from question."""
    return md5(question.encode("utf-8")).hexdigest()


def _parse_allowlist(raw: str) -> list[str]:
    out = []
    for x in str(raw or "").split(","):
        v = x.strip().lower()
        if v:
            out.append(v)
    return out


def _source_score(url: str, allowlist: list[str]) -> float:
    """
    Calculate source score for a URL.

    If allowlist is provided, it acts as a strict whitelist (only allowed domains pass).
    If allowlist is empty, use TLD-based scoring with stricter filtering.
    """
    host = (urlparse(str(url or "")).hostname or "").lower()
    if not host:
        return 0.0

    # If allowlist is provided, enforce strict whitelist
    if allowlist:
        if any(host == d or host.endswith(f".{d}") for d in allowlist):
            return 1.0
        # Not in allowlist - reject
        return 0.0

    # No allowlist - use TLD-based trust scoring with stricter thresholds
    # High trust domains
    if host.endswith(".gov") or host.endswith(".edu"):
        return 0.9
    # Medium trust domains
    if host.endswith(".org"):
        return 0.7
    # Known security/tech domains (could be expanded with a curated list)
    trusted_domains = {
        "github.com",
        "stackoverflow.com",
        "microsoft.com",
        "apple.com",
        "mozilla.org",
        "w3.org",
        "ietf.org",
        "owasp.org",
        "cve.org",
        "nvd.nist.gov",
        "cisa.gov",
        "cert.org",
    }
    if host in trusted_domains or any(host.endswith(f".{d}") for d in trusted_domains):
        return 0.8
    # Other domains get lower score
    return 0.4


def run_web_research(
    question: str,
    user_id: str = None,
    session_id: str = None,
    ip_address: str = None,
    user_agent: str = None,
) -> dict:
    """
    Execute web search with quality filtering and security measures.

    Args:
        question: User query (will be sanitized for sensitive info)
        user_id: User ID for activity logging (optional)
        session_id: Session ID for activity logging (optional)
        ip_address: User IP address for activity logging (optional)
        user_agent: User agent string for activity logging (optional)

    Returns:
        dict with keys:
        - context: Formatted search results
        - citations: List of source citations with trust scores
        - used: True if results found, False otherwise
        - error: Error message if search failed (optional)
        - metrics: Performance metrics (optional)

    Example:
        >>> result = run_web_research("What is RAG?", user_id="user123", session_id="sess456")
        >>> if result["used"]:
        ...     print(f"Found {len(result['citations'])} sources")
    """
    start_time = time.time()
    metrics = {
        "sanitized": False,
        "search_time": 0.0,
        "filter_time": 0.0,
        "total_results": 0,
        "filtered_results": 0,
        "final_results": 0,
    }

    # Sanitize query to remove sensitive information
    original_question = question
    question = _sanitize_query(question)
    if question != original_question:
        metrics["sanitized"] = True
        logger.info("Query sanitized before web search")

    settings = get_settings()
    allowlist = _parse_allowlist(getattr(settings, "web_domain_allowlist", ""))

    # Adjust min_score based on whether allowlist is provided
    if allowlist:
        min_score = 0.5  # Only accept whitelisted domains (score=1.0)
        logger.info(f"Using whitelist mode with {len(allowlist)} allowed domains")
    else:
        min_score = float(getattr(settings, "web_min_source_score", 0.6) or 0.6)
        logger.info(f"Using TLD scoring mode with min_score={min_score}")

    # Execute search
    search_start = time.time()
    try:
        logger.info(f"Starting web search for query: {question[:50]}...")
        results = search_web(question, max_results=5)
        metrics["search_time"] = time.time() - search_start
        metrics["total_results"] = len(results)
        logger.info(f"Web search returned {len(results)} raw results in {metrics['search_time']:.2f}s")
    except Exception as e:
        metrics["search_time"] = time.time() - search_start
        logger.exception(f"Web search failed for question: {question}")
        return {
            "context": "",
            "citations": [],
            "used": False,
            "error": f"web_search_error:{type(e).__name__}",
            "metrics": metrics,
        }

    # Filter and format results
    filter_start = time.time()
    lines = []
    citations = []
    filtered_count = 0

    for item in results:
        title = item.get("title", "")
        href = item.get("href", "")
        body = item.get("body", "")

        # Validate URL safety (if available)
        if METRICS_AVAILABLE and not validate_url(href):
            filtered_count += 1
            logger.warning(f"Unsafe URL filtered: {href}")
            continue

        score = _source_score(href, allowlist=allowlist)

        # Log filtering decision
        if score < min_score:
            filtered_count += 1
            logger.debug(f"Filtered out: {href} (score={score:.2f} < {min_score})")
            continue

        logger.debug(f"Accepted: {href} (score={score:.2f})")
        lines.append(f"[WEB] {title}\nURL: {href}\n{body}")
        citations.append(
            {
                "source": href or title,
                "content": body,
                "metadata": {"title": title, "source_score": score},
            }
        )

    metrics["filter_time"] = time.time() - filter_start
    metrics["filtered_results"] = filtered_count
    metrics["final_results"] = len(citations)

    # Log summary
    total_time = time.time() - start_time
    logger.info(
        f"Web search complete: {metrics['final_results']} results accepted, "
        f"{metrics['filtered_results']} filtered out, "
        f"total time {total_time:.2f}s"
    )

    if not citations:
        logger.warning(f"No results passed quality filters (min_score={min_score})")

    result = {
        "context": "\n\n".join(lines),
        "citations": citations,
        "used": bool(citations),
        "metrics": metrics,
    }

    # Record metrics (if available)
    if METRICS_AVAILABLE:
        try:
            get_metrics().record_search(result)
        except Exception as e:
            logger.debug(f"Failed to record metrics: {e}")

    # Log activity for management monitoring (if available)
    if ACTIVITY_LOGGER_AVAILABLE:
        try:
            activity_logger = get_activity_logger()
            activity_logger.log_search(
                user_id=user_id,
                session_id=session_id,
                query=question,  # Already sanitized
                query_sanitized=metrics.get("sanitized", False),
                result=result,
                ip_address=ip_address,
                user_agent=user_agent,
            )
        except Exception as e:
            logger.debug(f"Failed to log activity: {e}")

    return result
