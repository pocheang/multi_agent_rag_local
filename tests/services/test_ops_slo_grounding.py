"""The grounding SLO reports what it measured, and nothing when it measured nothing.

It used to filter audit rows on action ``query.run``, which no call site has ever
written -- the three ``query.*`` actions are recorded only when a query is
*refused*.  The list was therefore always empty, and an average over zero samples
was 1.0, so the operations page reported a perfect grounding ratio for a metric it
had never once observed.  A monitoring alert that cannot fire is worse than an
absent one: it reads as evidence that nothing is wrong.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime

from app.services.runtime.runtime_ops import build_ops_alerts


def _grounding_from_detail(detail: str | None) -> float | None:
    match = re.search(r"grounding_support=([0-9]*\.?[0-9]+)", str(detail or ""))
    return float(match.group(1)) if match else None


def _alerts(rows: list[dict[str, object]]) -> dict:
    return build_ops_alerts(
        generated_at=datetime.now(UTC),
        window_hours=24,
        window_rows=rows,
        request_rows=[],
        extract_grounding_support=_grounding_from_detail,
        p95_latency_threshold=5000,
        error_rate_threshold=100.0,
        grounding_threshold=0.6,
    )


def test_no_grounding_samples_reports_absence_not_a_perfect_score() -> None:
    payload = _alerts([{"action": "auth.login", "result": "success", "detail": "ok"}])

    assert payload["slo"]["grounding_support_ratio_avg"] is None
    assert [alert for alert in payload["alerts"] if alert["type"] == "grounding_support"] == []


def test_a_grounding_sample_below_the_threshold_still_alerts() -> None:
    payload = _alerts(
        [
            # Any row carrying the ratio counts: which action ends up recording it
            # is the open question, and the SLO no longer has to guess the name.
            {"action": "query.source_scope", "result": "success", "detail": "grounding_support=0.30"},
            {"action": "query.source_scope", "result": "success", "detail": "grounding_support=0.50"},
        ]
    )

    assert payload["slo"]["grounding_support_ratio_avg"] == 0.4
    grounding = [alert for alert in payload["alerts"] if alert["type"] == "grounding_support"]
    assert grounding and grounding[0]["value"] == 0.4
