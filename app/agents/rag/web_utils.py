"""URL validation and search metrics for the web research agent.

`app/agents/rag/web.py` imports `validate_url` and `get_metrics`; those are the
only two things here with a reader. Parallel search and a keyword freshness test
were listed here until 2026-09-06 and neither had ever run --
`run_parallel_web_research` built a `ThreadPoolExecutor` over `run_web_research`,
which is exactly the shape that wedged this process at zero CPU through
concurrent `DDGS()` construction (see Common Issues in CLAUDE.md), and
`is_time_sensitive_query` was an English-only duplicate of the bilingual pattern
`KnowledgeAgentService` actually consults.
"""

import logging

logger = logging.getLogger(__name__)


def validate_url(url: str) -> bool:
    """
    Validate if a URL is safe to access.

    Args:
        url: URL to validate

    Returns:
        True if URL is valid and safe, False otherwise
    """
    if not url:
        return False

    # Basic validation
    if not url.startswith(("http://", "https://")):
        return False

    # Check for suspicious patterns
    suspicious_patterns = [
        "javascript:",
        "data:",
        "file://",
        "localhost",
        "127.0.0.1",
        "0.0.0.0",
    ]

    url_lower = url.lower()
    for pattern in suspicious_patterns:
        if pattern in url_lower:
            logger.warning(f"Suspicious URL detected: {url}")
            return False

    return True


class WebSearchMetrics:
    """Track web search performance metrics."""

    def __init__(self):
        self.total_searches = 0
        self.successful_searches = 0
        self.failed_searches = 0
        self.total_results = 0
        self.filtered_results = 0
        self.total_time = 0.0
        self.sanitized_queries = 0

    def record_search(self, result: dict):
        """Record metrics from a search result."""
        self.total_searches += 1

        if result.get("used"):
            self.successful_searches += 1
        else:
            self.failed_searches += 1

        metrics = result.get("metrics", {})
        if metrics:
            self.total_results += metrics.get("total_results", 0)
            self.filtered_results += metrics.get("filtered_results", 0)
            self.total_time += metrics.get("search_time", 0.0) + metrics.get("filter_time", 0.0)
            if metrics.get("sanitized"):
                self.sanitized_queries += 1

    def get_success_rate(self) -> float:
        """Get success rate as percentage."""
        if self.total_searches == 0:
            return 0.0
        return (self.successful_searches / self.total_searches) * 100

    def get_average_time(self) -> float:
        """Get average search time in seconds."""
        if self.total_searches == 0:
            return 0.0
        return self.total_time / self.total_searches

    def get_filter_rate(self) -> float:
        """Get filter rate as percentage."""
        if self.total_results == 0:
            return 0.0
        return (self.filtered_results / self.total_results) * 100

    def get_summary(self) -> dict:
        """Get summary of all metrics."""
        return {
            "total_searches": self.total_searches,
            "successful_searches": self.successful_searches,
            "failed_searches": self.failed_searches,
            "success_rate": round(self.get_success_rate(), 2),
            "total_results": self.total_results,
            "filtered_results": self.filtered_results,
            "filter_rate": round(self.get_filter_rate(), 2),
            "average_time": round(self.get_average_time(), 2),
            "sanitized_queries": self.sanitized_queries,
        }

    def __str__(self) -> str:
        """String representation of metrics."""
        summary = self.get_summary()
        return (
            f"Web Search Metrics:\n"
            f"  Total: {summary['total_searches']} "
            f"(Success: {summary['successful_searches']}, "
            f"Failed: {summary['failed_searches']})\n"
            f"  Success Rate: {summary['success_rate']}%\n"
            f"  Results: {summary['total_results']} total, "
            f"{summary['filtered_results']} filtered ({summary['filter_rate']}%)\n"
            f"  Avg Time: {summary['average_time']}s\n"
            f"  Sanitized: {summary['sanitized_queries']} queries"
        )


# Global metrics instance
_global_metrics = WebSearchMetrics()


def get_metrics() -> WebSearchMetrics:
    """Get global metrics instance."""
    return _global_metrics
