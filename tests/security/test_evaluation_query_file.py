"""The evaluation endpoints choose which file, never where.

`pythonsecurity:S6549` pointed at `_resolve_query_file`. The check it had was
correct -- resolve, then require a `.json` suffix and `is_relative_to` the
evaluation root -- but the shape was build-then-check: the API accepted an
absolute path to anywhere on the filesystem and depended entirely on that one
condition to turn it down. Nothing stood between a caller and the disk except a
predicate somebody could edit.

It now takes a file name, matched against an allow-list pattern, joined under a
root the caller cannot influence. These tests pin what that has to mean, in both
directions: nothing escapes the root, and the shapes that used to work still do.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import HTTPException

from app.api.routes.operations.evaluation import _EVALUATION_ROOT, _resolve_query_file


def _rejected(value: str) -> bool:
    try:
        _resolve_query_file(value)
    except HTTPException as exc:
        assert exc.status_code == 400
        return True
    return False


class TestNothingEscapesTheEvaluationDirectory:
    @pytest.mark.parametrize(
        "value",
        [
            "../../../etc/passwd.json",
            "..\\..\\windows\\system.json",
            "/etc/passwd.json",
            "C:\\Windows\\system.json",
            "sub/dir/queries.json",
            "data/evaluation/demo_queries.json",  # the old default: a path, so now refused
        ],
    )
    def test_anything_carrying_a_separator_is_refused(self, value: str) -> None:
        """Refused rather than reduced to its last segment.

        Reading `/etc/passwd.json` as `data/evaluation/passwd.json` would also be
        safe, and would tell a caller that asked for something impossible that it
        had got what it asked for.
        """

        assert _rejected(value)

    @pytest.mark.parametrize("value", ["", "queries", "queries.txt", "queries.json.exe", ".json", "-x.json"])
    def test_anything_that_is_not_a_json_file_name_is_refused(self, value: str) -> None:
        assert _rejected(value)

    def test_an_accepted_name_lands_directly_in_the_root(self) -> None:
        resolved = Path(_resolve_query_file("demo_queries.json"))

        assert resolved.parent == _EVALUATION_ROOT
        assert resolved.name == "demo_queries.json"


class TestOrdinaryNamesStillWork:
    @pytest.mark.parametrize("value", ["demo_queries.json", "a.json", "set-2.json", "set_2.v3.json"])
    def test_a_plain_file_name_resolves(self, value: str) -> None:
        assert Path(_resolve_query_file(value)).parent == _EVALUATION_ROOT

    def test_the_endpoint_defaults_are_accepted_by_their_own_validator(self) -> None:
        """A default the validator rejects would make every call fail on its
        documented behaviour, which is exactly the sort of thing changing the
        defaults alongside the rule can cause."""

        from app.api.routes.operations import evaluation

        defaults = [
            evaluation.RunEvaluationRequest.model_fields["query_file"].default,
            evaluation.CompareSystemsRequest.model_fields["query_file"].default,
        ]
        for default in defaults:
            assert not _rejected(default), f"the shipped default {default!r} is rejected by _resolve_query_file"
