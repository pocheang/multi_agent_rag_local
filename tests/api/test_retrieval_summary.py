"""The badge has to say what the run actually did.

Every answer displayed `web: no`, including ones written entirely from web
results. Neither entry point ever set the field:

- `query.py::_response_metadata` had no `web_used` key at all, so the client
  defaulted a missing value to False;
- `sessions.py` read `result["web_result"]["used"]` and
  `result["graph_result"]["entities"]` off a shape
  `execute_standard_compatibility` does not return, so the rerun path recorded
  False and an empty list on every message.

It is not only a badge. `score_memory_candidate` weights `web_used` at 0.20
(`0.20 * (0.0 if web_used else 1.0)`), so every long-term memory candidate has
been scored as though the answer were purely local.
"""

from __future__ import annotations

import pytest

from app.api.routes.internal.pipeline_contract import retrieval_summary


def _metadata(status: dict[str, str], counts: dict[str, int], errors: dict[str, str] | None = None) -> dict:
    return {
        "workflow_diagnostics": {
            "knowledge_diagnostics": {
                "source_status": status,
                "source_result_count": counts,
                "source_error_type": errors or {},
            }
        }
    }


EMPTY_CORPUS = _metadata(
    {"vector": "skipped", "bm25": "skipped", "web": "completed"},
    {"vector": 0, "bm25": 0, "web": 4},
    {"vector": "EmptyAccessScope", "bm25": "EmptyAccessScope"},
)


class TestWhatCountsAsUsed:
    def test_web_evidence_makes_web_used_true(self) -> None:
        assert retrieval_summary(EMPTY_CORPUS)["web_used"] is True

    def test_a_search_that_found_nothing_is_not_a_source(self) -> None:
        """ "Ran" and "contributed" are different claims, and the badge makes the
        second one. A web search returning nothing is not what a reader means by
        "this answer used the web"."""
        summary = retrieval_summary(_metadata({"vector": "completed", "web": "completed"}, {"vector": 3, "web": 0}))

        assert summary["web_used"] is False
        assert summary["contributing_sources"] == ["vector"]

    def test_a_source_that_ran_empty_is_still_reported(self) -> None:
        """It explains a thin answer, so it stays in `sources` even though it is
        not a contributor."""
        summary = retrieval_summary(_metadata({"vector": "completed", "web": "completed"}, {"vector": 3, "web": 0}))

        assert {item["source"] for item in summary["sources"]} == {"vector", "web"}

    def test_the_skip_reason_survives(self) -> None:
        """`EmptyAccessScope` is not a failure, and the client should be able to
        tell the difference."""
        summary = retrieval_summary(EMPTY_CORPUS)
        reasons = {item["source"]: item["reason"] for item in summary["sources"]}

        assert reasons["vector"] == "EmptyAccessScope"
        assert reasons["web"] is None


class TestItDoesNotInventAnything:
    @pytest.mark.parametrize(
        "metadata", [{}, {"workflow_diagnostics": {}}, {"workflow_diagnostics": {"knowledge_diagnostics": {}}}]
    )
    def test_missing_diagnostics_claim_nothing(self, metadata: dict) -> None:
        summary = retrieval_summary(metadata)

        assert summary == {"web_used": False, "sources": [], "contributing_sources": []}


class TestBothEntryPointsReportIt:
    """CLAUDE.md: the chat endpoint and the rerun endpoint must produce
    identically shaped history rows."""

    def test_the_chat_endpoint_includes_the_summary(self) -> None:
        from app.api.routes.public.query import _response_metadata

        metadata = _response_metadata(
            pipeline_result_metadata=EMPTY_CORPUS,
            route="vector",
            citations=[],
            tool_runs=[],
            execution_id="exec-1",
            session_id=None,
        )

        assert metadata["web_used"] is True
        assert metadata["contributing_sources"] == ["web"]

    def test_the_rerun_path_reads_a_shape_that_exists(self) -> None:
        """The bug was reading `web_result`/`graph_result` off a return value
        that had neither key, so the defaults were the only values ever seen."""
        import inspect

        from app.api.routes.internal import pipeline_contract

        source = inspect.getsource(pipeline_contract.execute_standard_compatibility)

        assert '"web_result"' in source
        assert '"graph_result"' in source
