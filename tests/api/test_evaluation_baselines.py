"""The evaluation baselines must return a result, not raise.

Both baselines built ``RetrievalResult(query_id=..., query=query, ...)`` while the
required field is ``query_text``, so pydantic raised for a missing field on every
query, for every baseline -- ``POST /api/evaluation/run`` and ``/compare`` could
not complete at all.

It survived because the mistake was made twice.  The happy path's ValidationError
was swallowed by a bare ``except Exception``, whose handler then re-made the
identical mistake *outside* the try, where nothing could catch it.  So the tests
here are parametrized over ``SUPPORTED_SYSTEMS`` rather than written once per
baseline: the defect was two call sites having to agree, and a third baseline
would have had to agree too.

Nothing on the request path imports this module, which is why nobody saw it.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.evaluation.baselines import api_retriever
from app.evaluation.baselines.api_retriever import SUPPORTED_SYSTEMS, SimpleRetriever

# Aliased: pytest tries to collect any imported name starting with "Test".
from app.evaluation.models import RetrievalResult
from app.evaluation.models import TestQuery as EvalQuery
from app.evaluation.service import EvaluationService

QUERY = "what does the handbook say about leave"
QUERY_ID = "q-1"


class _Document:
    """The shape `similarity_search` returns: an object carrying `.metadata`."""

    def __init__(self, source: str) -> None:
        self.metadata = {"source": source}


@pytest.fixture
def stubbed_stores(monkeypatch) -> None:
    """Answer both baselines without a vector store, an index, or a model."""

    monkeypatch.setattr(
        api_retriever,
        "similarity_search",
        lambda **kwargs: [(_Document("/docs/handbook.md"), 0.9)],
    )
    monkeypatch.setattr(
        api_retriever,
        "hybrid_search_with_diagnostics",
        lambda **kwargs: ([{"source": "/docs/handbook.md"}], {}),
    )


@pytest.mark.parametrize("system_name", SUPPORTED_SYSTEMS)
def test_every_supported_baseline_constructs_a_valid_result(system_name: str, stubbed_stores: None) -> None:
    """The assertion that would have caught it: the result must actually build.

    Parametrized over the tuple rather than written per baseline, so a third
    baseline is covered the day it is declared.
    """

    result = SimpleRetriever(system_name).retrieve(QUERY, QUERY_ID)

    assert isinstance(result, RetrievalResult)
    assert result.query_text == QUERY
    assert result.query_id == QUERY_ID
    assert result.retrieved_docs == ["/docs/handbook.md"]


@pytest.mark.parametrize("system_name", SUPPORTED_SYSTEMS)
def test_a_retrieval_error_returns_a_result_rather_than_raising(system_name: str, monkeypatch) -> None:
    """The failure path is the one that had no `except` above it."""

    def explode(**kwargs: Any) -> Any:
        raise RuntimeError("store unavailable")

    monkeypatch.setattr(api_retriever, "similarity_search", explode)
    monkeypatch.setattr(api_retriever, "hybrid_search_with_diagnostics", explode)

    result = SimpleRetriever(system_name).retrieve(QUERY, QUERY_ID)

    assert result.query_text == QUERY
    assert result.retrieved_docs == []


def test_an_unknown_system_is_reported_as_a_result_not_a_crash(stubbed_stores: None) -> None:
    """`retrieve` raises ValueError internally for an unknown name; the handler
    still has to produce a result, because `batch_retrieve` has no other path."""

    result = SimpleRetriever("not_a_baseline").retrieve(QUERY, QUERY_ID)

    assert result.query_text == QUERY
    assert result.retrieved_docs == []


def test_a_short_result_list_is_an_error_not_a_truncation() -> None:
    """Truncation *improves* the score: the dropped queries are the failures.

    `evaluate_system` zipped with `strict=False`, so a retriever returning fewer
    results than it was given queries silently scored only the prefix.
    """

    queries = [
        EvalQuery(id="q-1", query="one", category="test", expected_docs=["/docs/a.md"]),
        EvalQuery(id="q-2", query="two", category="test", expected_docs=["/docs/b.md"]),
    ]

    class _ShortRetriever:
        def retrieve(self, query: str, query_id: str = "") -> RetrievalResult:  # pragma: no cover - unused
            raise NotImplementedError

        def batch_retrieve(self, batch: list[tuple[str, str]]) -> list[RetrievalResult]:
            return [RetrievalResult(query_id="q-1", query_text="one", retrieved_docs=["/docs/a.md"], latency_ms=1.0)]

    with pytest.raises(ValueError):
        EvaluationService().evaluate_system(_ShortRetriever(), queries, "short")
