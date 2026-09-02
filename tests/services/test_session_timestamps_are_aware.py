"""Session metadata timestamps are aware, whatever the database holds.

`python:S6903` flagged seven `datetime.utcnow()` calls as deprecated. The
deprecation is the least of it: `utcnow()` returns a *naive* datetime, and a
naive one beside an aware one in the same comparison raises

    TypeError: can't compare offset-naive and offset-aware datetimes

`search.py::_sort_results` sorts SearchResult objects on
`metadata.updated_at`, so that comparison is one `sorted()` away from a 500 on
session search. It had never fired because every writer was consistently naive.

Which is what makes the obvious fix the dangerous one. Switching the writers to
`datetime.now(UTC)` and stopping there would have *created* the mix it was
meant to avoid: rows written before the change parse back naive, rows after come
back aware, and the first search that spans both raises. So the read path
normalises too, and these tests are mostly about that half.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.services.sessions.metadata import SessionMetadata, as_utc, utc_now


class TestTimestampsAreWrittenAware:
    def test_utc_now_is_aware(self) -> None:
        assert utc_now().tzinfo is not None

    def test_a_fresh_metadata_object_is_aware(self) -> None:
        metadata = SessionMetadata(session_id="s1")

        assert metadata.created_at.tzinfo is not None
        assert metadata.updated_at.tzinfo is not None


class TestTimestampsAreReadAware:
    def test_a_naive_value_is_read_as_utc(self) -> None:
        """A row written before 2026-09-02."""

        naive = datetime(2026, 7, 1, 12, 0, 0)  # noqa: DTZ001 -- the shape being fixed
        assert as_utc(naive) == datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)

    def test_an_aware_value_survives(self) -> None:
        aware = datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)

        assert as_utc(aware) is aware or as_utc(aware) == aware

    def test_the_database_read_path_normalises(self) -> None:
        from app.services.sessions.metadata_db import SessionMetadataDB

        row = {
            "session_id": "s1",
            "tags": "[]",
            "category": "general",
            "description": "",
            "auto_tags": "[]",
            "created_at": "2026-07-01T12:00:00",  # no offset: written by the old code
            "updated_at": "2026-07-01T12:00:00",
            "query_count": 0,
            "last_query_at": "2026-07-01T12:00:00",
        }

        metadata = SessionMetadataDB._deserialize_row(SessionMetadataDB.__new__(SessionMetadataDB), row)

        assert metadata.created_at.tzinfo is not None
        assert metadata.updated_at.tzinfo is not None
        assert metadata.last_query_at is not None and metadata.last_query_at.tzinfo is not None


class TestTheMixCannotReachASort:
    def test_old_and_new_rows_sort_together(self) -> None:
        """The failure this whole change exists to prevent.

        Without normalisation on read this raises rather than fails an
        assertion, which is what it would do behind session search.
        """

        old = SessionMetadata(session_id="old", updated_at=as_utc(datetime(2026, 7, 1)))  # noqa: DTZ001
        new = SessionMetadata(session_id="new")

        ordered = sorted([new, old], key=lambda m: m.updated_at)

        assert [m.session_id for m in ordered] == ["old", "new"]

    def test_an_unnormalised_naive_value_would_still_raise(self) -> None:
        """Pins *why* the read path has to normalise, rather than trusting that
        it does: this is the exception the production path would have thrown."""

        naive = SessionMetadata(session_id="old", updated_at=datetime(2026, 7, 1))  # noqa: DTZ001
        aware = SessionMetadata(session_id="new")

        with pytest.raises(TypeError, match="offset-naive and offset-aware"):
            sorted([aware, naive], key=lambda m: m.updated_at)
