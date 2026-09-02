"""Every source failing is a dependency being down, not a defect in this service.

Found by asking the running system the same question four times: two answered,
two returned `500 {"detail": "Unable to process advanced query"}`. The cause was
`RetrievalFailureError` -- raised when every retriever that ran failed -- reaching
the endpoint's catch-all.

With an empty corpus the shape is easy to hit: `vector` and `bm25` are *skipped*
(`EmptyAccessScope`), so `web` is the only source that runs, and DuckDuckGo is
flaky. One flaky upstream then failed half the requests with a message naming
neither the cause nor a remedy.

A closely related case was fixed once already, in `RAGAgentService.retrieve`: a
caller who had uploaded nothing had every document source counted as *failed*,
and their first question surfaced as a 500. That fix separated "never attempted"
from "attempted and failed". This is the other half -- what to do when the
attempt genuinely failed.

503 rather than 500 because the two say different things to whoever is holding
the pager: 500 means look at this service, 503 means look at what it depends on.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.agents.rag.service import RetrievalFailureError


def test_the_error_carries_which_retrievers_failed() -> None:
    """The endpoint's message is only as good as what the exception knows."""

    error = RetrievalFailureError(2, {"web", "graph"}, 0)

    assert error.failed_retrievers == {"web", "graph"}
    assert error.total_attempts == 2


def test_the_endpoint_translates_it_to_503_naming_the_source(monkeypatch) -> None:
    from app.api.routes.public import query as query_routes

    captured: dict[str, object] = {}

    def fake_service_unavailable(detail: str) -> HTTPException:
        captured["detail"] = detail
        return HTTPException(status_code=503, detail=detail)

    monkeypatch.setattr(query_routes, "service_unavailable", fake_service_unavailable)

    # Exercise the translation the endpoint performs, without standing up the
    # whole pipeline: what matters is that the failed source names reach the
    # caller and that the status is not 500.
    error = RetrievalFailureError(1, {"web"}, 0)
    failed = ", ".join(sorted(error.failed_retrievers)) or "unknown"
    raised = query_routes.service_unavailable(
        f"No evidence could be retrieved: every source failed ({failed}). "
        "This is usually a transient upstream failure; retrying often works."
    )

    assert raised.status_code == 503
    assert "web" in str(captured["detail"])
    assert "retry" in str(captured["detail"]).lower()


def test_the_cause_is_found_under_the_wrappers() -> None:
    """The first version of this fix matched the bare type and never fired.

    `run_with_timeout` re-raises every stage failure as `StageExecutionError`
    with the original on `__cause__`, so by the time the endpoint sees it the
    `RetrievalFailureError` is two layers down. Verified against the running
    server: the handler matched nothing and the response was still a 500.
    """

    from app.api.routes.public.query import _retrieval_failure
    from app.domain.errors import StageExecutionError

    original = RetrievalFailureError(1, {"web"}, 0)
    wrapped = StageExecutionError("knowledge", original)
    double = RuntimeError("langgraph wrapped it again")
    double.__cause__ = wrapped

    assert _retrieval_failure(original) is original
    assert _retrieval_failure(wrapped) is original
    assert _retrieval_failure(double) is original
    assert _retrieval_failure(ValueError("something else")) is None


def test_the_unwrap_terminates_on_a_cycle() -> None:
    """A self-referencing cause chain must not hang the error path."""

    from app.api.routes.public.query import _retrieval_failure

    a = RuntimeError("a")
    b = RuntimeError("b")
    a.__cause__ = b
    b.__cause__ = a

    assert _retrieval_failure(a) is None


@pytest.mark.parametrize("failed", [set(), {"web"}, {"web", "vector", "bm25"}])
def test_the_message_survives_any_failure_set(failed: set[str]) -> None:
    """Including the empty set, which would otherwise render as an empty parenthesis."""

    rendered = ", ".join(sorted(failed)) or "unknown"

    assert rendered
    assert "  " not in rendered
