"""
Unit tests for Web Research Agent

Tests cover:
- Query sanitization
- URL validation
- Source scoring
- Search execution
- Metrics tracking
"""

import pytest
from app.agents.web_research_agent import (
    _sanitize_query,
    _source_score,
    _parse_allowlist,
    run_web_research,
)
from app.agents.web_research_utils import (
    validate_url,
    is_time_sensitive_query,
    WebSearchMetrics,
)


class TestQuerySanitization:
    """Test query sanitization functionality."""

    def test_sanitize_email(self):
        """Test email sanitization."""
        query = "Contact john.doe@example.com for info"
        result = _sanitize_query(query)
        assert "john.doe@example.com" not in result
        assert "[REDACTED_EMAIL]" in result

    def test_sanitize_ip_address(self):
        """Test IP address sanitization."""
        query = "Server at 192.168.1.1 is down"
        result = _sanitize_query(query)
        assert "192.168.1.1" not in result
        assert "[REDACTED_IP]" in result

    def test_sanitize_password(self):
        """Test password sanitization."""
        query = "password=secret123"
        result = _sanitize_query(query)
        assert "secret123" not in result
        assert "[REDACTED]" in result

    def test_sanitize_api_key(self):
        """Test API key sanitization."""
        query = "api_key=abc123xyz"
        result = _sanitize_query(query)
        assert "abc123xyz" not in result
        assert "[REDACTED]" in result

    def test_no_sanitization_needed(self):
        """Test query that doesn't need sanitization."""
        query = "What is machine learning?"
        result = _sanitize_query(query)
        assert result == query


class TestURLValidation:
    """Test URL validation functionality."""

    def test_valid_https_url(self):
        """Test valid HTTPS URL."""
        assert validate_url("https://example.com") is True

    def test_valid_http_url(self):
        """Test valid HTTP URL."""
        assert validate_url("http://example.com") is True

    def test_invalid_javascript_url(self):
        """Test invalid JavaScript URL."""
        assert validate_url("javascript:alert('xss')") is False

    def test_invalid_localhost(self):
        """Test invalid localhost URL."""
        assert validate_url("http://localhost:8080") is False

    def test_invalid_local_ip(self):
        """Test invalid local IP URL."""
        assert validate_url("http://127.0.0.1") is False

    def test_empty_url(self):
        """Test empty URL."""
        assert validate_url("") is False


class TestSourceScoring:
    """Test source scoring functionality."""

    def test_gov_domain_score(self):
        """Test .gov domain gets high score."""
        score = _source_score("https://cisa.gov/alert", allowlist=[])
        assert score == 0.9

    def test_edu_domain_score(self):
        """Test .edu domain gets high score."""
        score = _source_score("https://mit.edu/research", allowlist=[])
        assert score == 0.9

    def test_org_domain_score(self):
        """Test .org domain gets medium score."""
        score = _source_score("https://mozilla.org/firefox", allowlist=[])
        assert score == 0.7

    def test_trusted_domain_score(self):
        """Test trusted domain gets high score."""
        score = _source_score("https://github.com/repo", allowlist=[])
        assert score == 0.8

    def test_generic_domain_score(self):
        """Test generic domain gets low score."""
        score = _source_score("https://example.com/page", allowlist=[])
        assert score == 0.4

    def test_whitelist_mode_accepted(self):
        """Test whitelist mode accepts listed domain."""
        score = _source_score("https://github.com/repo", allowlist=["github.com"])
        assert score == 1.0

    def test_whitelist_mode_rejected(self):
        """Test whitelist mode rejects unlisted domain."""
        score = _source_score("https://example.com/page", allowlist=["github.com"])
        assert score == 0.0


class TestAllowlistParsing:
    """Test allowlist parsing functionality."""

    def test_parse_comma_separated(self):
        """Test parsing comma-separated domains."""
        result = _parse_allowlist("github.com,stackoverflow.com,owasp.org")
        assert result == ["github.com", "stackoverflow.com", "owasp.org"]

    def test_parse_with_spaces(self):
        """Test parsing with extra spaces."""
        result = _parse_allowlist("github.com , stackoverflow.com , owasp.org")
        assert result == ["github.com", "stackoverflow.com", "owasp.org"]

    def test_parse_empty_string(self):
        """Test parsing empty string."""
        result = _parse_allowlist("")
        assert result == []

    def test_parse_none(self):
        """Test parsing None."""
        result = _parse_allowlist(None)
        assert result == []


class TestTimeSensitiveDetection:
    """Test time-sensitive query detection."""

    def test_detect_latest_keyword(self):
        """Test detection of 'latest' keyword."""
        assert is_time_sensitive_query("What is the latest AI news?") is True

    def test_detect_today_keyword(self):
        """Test detection of 'today' keyword."""
        assert is_time_sensitive_query("Stock prices today") is True

    def test_detect_chinese_keyword(self):
        """Test detection of Chinese time keywords."""
        assert is_time_sensitive_query("今天的天气如何？") is True

    def test_detect_year(self):
        """Test detection of current year."""
        assert is_time_sensitive_query("2026 AI trends") is True

    def test_non_time_sensitive(self):
        """Test non-time-sensitive query."""
        assert is_time_sensitive_query("What is Python?") is False


class TestMetricsTracking:
    """Test metrics tracking functionality."""

    def test_metrics_initialization(self):
        """Test metrics object initialization."""
        metrics = WebSearchMetrics()
        assert metrics.total_searches == 0
        assert metrics.successful_searches == 0
        assert metrics.failed_searches == 0

    def test_record_successful_search(self):
        """Test recording successful search."""
        metrics = WebSearchMetrics()
        result = {
            "used": True,
            "metrics": {
                "total_results": 5,
                "filtered_results": 2,
                "search_time": 1.5,
                "filter_time": 0.2,
                "sanitized": False,
            }
        }
        metrics.record_search(result)

        assert metrics.total_searches == 1
        assert metrics.successful_searches == 1
        assert metrics.failed_searches == 0
        assert metrics.total_results == 5
        assert metrics.filtered_results == 2

    def test_record_failed_search(self):
        """Test recording failed search."""
        metrics = WebSearchMetrics()
        result = {
            "used": False,
            "metrics": {}
        }
        metrics.record_search(result)

        assert metrics.total_searches == 1
        assert metrics.successful_searches == 0
        assert metrics.failed_searches == 1

    def test_success_rate_calculation(self):
        """Test success rate calculation."""
        metrics = WebSearchMetrics()
        metrics.total_searches = 10
        metrics.successful_searches = 7

        assert metrics.get_success_rate() == 70.0

    def test_average_time_calculation(self):
        """Test average time calculation."""
        metrics = WebSearchMetrics()
        metrics.total_searches = 5
        metrics.total_time = 10.0

        assert metrics.get_average_time() == 2.0

    def test_filter_rate_calculation(self):
        """Test filter rate calculation."""
        metrics = WebSearchMetrics()
        metrics.total_results = 10
        metrics.filtered_results = 3

        assert metrics.get_filter_rate() == 30.0

    def test_metrics_summary(self):
        """Test metrics summary generation."""
        metrics = WebSearchMetrics()
        metrics.total_searches = 10
        metrics.successful_searches = 8
        metrics.failed_searches = 2
        metrics.total_results = 50
        metrics.filtered_results = 15
        metrics.total_time = 20.0
        metrics.sanitized_queries = 2

        summary = metrics.get_summary()

        assert summary["total_searches"] == 10
        assert summary["successful_searches"] == 8
        assert summary["success_rate"] == 80.0
        assert summary["filter_rate"] == 30.0
        assert summary["average_time"] == 2.0
        assert summary["sanitized_queries"] == 2


class TestWebResearchIntegration:
    """Integration tests for web research agent."""

    @pytest.mark.skip(reason="Requires external API access")
    def test_run_web_research_basic(self):
        """Test basic web research execution."""
        result = run_web_research("What is RAG in AI?")

        assert "context" in result
        assert "citations" in result
        assert "used" in result
        assert "metrics" in result

    @pytest.mark.skip(reason="Requires external API access")
    def test_run_web_research_with_sensitive_data(self):
        """Test web research with sensitive data."""
        result = run_web_research("Contact admin@example.com about 192.168.1.1")

        # Query should be sanitized
        assert result["metrics"]["sanitized"] is True

    @pytest.mark.skip(reason="Requires external API access")
    def test_run_web_research_metrics(self):
        """Test web research returns metrics."""
        result = run_web_research("Python programming")

        metrics = result.get("metrics", {})
        assert "search_time" in metrics
        assert "filter_time" in metrics
        assert "total_results" in metrics
        assert "final_results" in metrics


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
