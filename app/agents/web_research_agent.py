import logging
from urllib.parse import urlparse

from app.core.config import get_settings
from app.tools.web_search import search_web

logger = logging.getLogger(__name__)


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
        "github.com", "stackoverflow.com", "microsoft.com", "apple.com",
        "mozilla.org", "w3.org", "ietf.org", "owasp.org", "cve.org",
        "nvd.nist.gov", "cisa.gov", "cert.org"
    }
    if host in trusted_domains or any(host.endswith(f".{d}") for d in trusted_domains):
        return 0.8
    # Other domains get lower score
    return 0.4


def run_web_research(question: str) -> dict:
    settings = get_settings()
    allowlist = _parse_allowlist(getattr(settings, "web_domain_allowlist", ""))
    # Adjust min_score based on whether allowlist is provided
    # With allowlist: strict whitelist (score is 0.0 or 1.0)
    # Without allowlist: use higher threshold to filter low-quality sources
    if allowlist:
        min_score = 0.5  # Only accept whitelisted domains (score=1.0)
    else:
        min_score = float(getattr(settings, "web_min_source_score", 0.6) or 0.6)

    try:
        results = search_web(question, max_results=5)
    except Exception as e:
        logger.exception(f"Web search failed for question: {question}")
        return {
            "context": "",
            "citations": [],
            "used": False,
            "error": f"web_search_error:{type(e).__name__}",
        }

    lines = []
    citations = []
    for item in results:
        title = item.get("title", "")
        href = item.get("href", "")
        body = item.get("body", "")
        score = _source_score(href, allowlist=allowlist)
        if score < min_score:
            continue
        lines.append(f"[WEB] {title}\nURL: {href}\n{body}")
        citations.append(
            {
                "source": href or title,
                "content": body,
                "metadata": {"title": title, "source_score": score},
            }
        )
    return {"context": "\n\n".join(lines), "citations": citations, "used": bool(citations)}
