"""The grounding SLO measures answers, and reports nothing when it measured none.

It used to average the ratio over *audit* rows with action ``query.run``, which
no call site has ever written -- the three ``query.*`` actions are recorded only
when a query is refused.  The list was therefore always empty, and an average
over zero samples was 1.0, so the operations page reported a perfect grounding
ratio for a metric it had never once observed.  An alert that cannot fire is
worse than an absent one: it reads as evidence that nothing is wrong.

The value now rides the request's own metrics row, the same window the p95 is
computed from.  The first test below covers the plumbing that makes that
possible, which is the part that is easy to get wrong and impossible to see:
``request.state`` survives the hop back up to the middleware, and a ContextVar
would not.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from app.api.transport.middleware import (
    get_request_metrics,
    record_grounding_support,
    request_timing_middleware,
)
from app.services.runtime.runtime_ops import build_ops_alerts


def _alerts(request_rows: list[dict[str, object]]) -> dict:
    return build_ops_alerts(
        generated_at=datetime.now(UTC),
        window_hours=24,
        window_rows=[],
        request_rows=request_rows,
        p95_latency_threshold=5000,
        error_rate_threshold=100.0,
        grounding_threshold=0.6,
    )


def test_the_ratio_reaches_the_metrics_row_the_middleware_writes() -> None:
    """The endpoint writes it downstream; the middleware reads it back upstream."""

    app = FastAPI()
    app.middleware("http")(request_timing_middleware)

    @app.get("/answered")
    def answered(request: Request) -> dict[str, str]:
        record_grounding_support(request, {"grounding": {"support_ratio": 0.75}})
        return {"ok": "yes"}

    @app.get("/not-an-answer")
    def not_an_answer() -> dict[str, str]:
        return {"ok": "yes"}

    client = TestClient(app)
    assert client.get("/answered").status_code == 200
    assert client.get("/not-an-answer").status_code == 200

    rows = {row["path"]: row for row in get_request_metrics()}
    assert rows["/answered"]["grounding_support"] == 0.75
    assert rows["/not-an-answer"]["grounding_support"] is None


def test_no_grounding_samples_reports_absence_not_a_perfect_score() -> None:
    payload = _alerts([{"path": "/health", "duration_ms": 3, "grounding_support": None}])

    assert payload["slo"]["grounding_support_ratio_avg"] is None
    assert [alert for alert in payload["alerts"] if alert["type"] == "grounding_support"] == []


def test_a_sample_below_the_threshold_still_alerts() -> None:
    payload = _alerts(
        [
            {"path": "/api/advanced-rag/query", "duration_ms": 900, "grounding_support": 0.30},
            {"path": "/api/advanced-rag/query", "duration_ms": 900, "grounding_support": 0.50},
            {"path": "/health", "duration_ms": 2, "grounding_support": None},
        ]
    )

    assert payload["slo"]["grounding_support_ratio_avg"] == 0.4
    grounding = [alert for alert in payload["alerts"] if alert["type"] == "grounding_support"]
    assert grounding and grounding[0]["value"] == 0.4
