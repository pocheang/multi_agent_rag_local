"""Structured clarification answers are read one line at a time.

`_structured_fields` parses `- field: value` out of text the user typed, and its
pattern used `\\s*` between the parts. `\\s` matches a newline, and the pattern
runs under `(?m)`, so a bare dash on one line could be paired with a field name
several lines below it -- the user writes a list item and a heading, and the
parser reads a value they never gave that field.

That is also where the backtracking came from (python:S8786): from every line
start, `\\s*` could run to the end of the text before giving up. 800 lines of
whitespace took 117ms; the same input takes 0.4ms now. The timing is not what
these tests assert -- a clock is a bad thing to assert on in CI -- but the
one-line rule that removed it is deterministic, and that is what is pinned here.
"""

from __future__ import annotations

import pytest

from app.agents.clarification.rules import _QUESTIONS_ZH, _structured_fields

FIELD = sorted({name for questions in _QUESTIONS_ZH.values() for name in questions})[0]


def test_a_field_and_its_value_are_read_from_one_line() -> None:
    assert _structured_fields(f"- {FIELD}: hello") == {FIELD: "hello"}


@pytest.mark.parametrize(
    "text",
    [
        "  - {field}: hello",
        "-   {field}   :   hello",
        "- {field}: hello   ",
        "intro line\n- {field}: hello\ntrailing line",
    ],
)
def test_ordinary_spacing_around_the_parts_still_parses(text: str) -> None:
    assert _structured_fields(text.format(field=FIELD)) == {FIELD: "hello"}


def test_a_dash_on_one_line_does_not_claim_a_field_from_another() -> None:
    """The old pattern read this as `{FIELD}: hello`, from two different lines."""

    assert _structured_fields(f"-\n\n{FIELD}: hello") == {}


def test_a_field_name_nothing_asks_about_is_ignored() -> None:
    assert _structured_fields("- not_a_field: hello") == {}


def test_a_field_with_no_value_is_not_recorded() -> None:
    assert _structured_fields(f"- {FIELD}:   ") == {}


def test_several_fields_are_read_independently() -> None:
    names = sorted({name for questions in _QUESTIONS_ZH.values() for name in questions})[:2]
    text = "\n".join(f"- {name}: value-{index}" for index, name in enumerate(names))

    assert _structured_fields(text) == {name: f"value-{index}" for index, name in enumerate(names)}
