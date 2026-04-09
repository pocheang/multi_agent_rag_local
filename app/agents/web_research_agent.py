from urllib.parse import urlparse

from app.core.config import get_settings
from app.tools.web_search import search_web


def _parse_allowlist(raw: str) -> list[str]:
    out = []
    for x in str(raw or "").split(","):
        v = x.strip().lower()
        if v:
            out.append(v)
    return out


def _source_score(url: str, allowlist: list[str]) -> float:
    host = (urlparse(str(url or "")).hostname or "").lower()
    if not host:
        return 0.0
    if any(host == d or host.endswith(f".{d}") for d in allowlist):
        return 1.0
    if host.endswith(".gov") or host.endswith(".edu"):
        return 0.8
    if host.endswith(".org"):
        return 0.6
    return 0.1


def run_web_research(question: str) -> dict:
    settings = get_settings()
    allowlist = _parse_allowlist(getattr(settings, "web_domain_allowlist", ""))
    min_score = float(getattr(settings, "web_min_source_score", 0.2) or 0.2)
    results = search_web(question, max_results=5)
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
