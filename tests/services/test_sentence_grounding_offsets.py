"""A hedge must land between sentences, not inside a word.

`apply_sentence_grounding` scores each sentence against the evidence and splices
a hedge in front of the weak ones. It splices **by offset** into the raw answer,
and the offsets come from `_sentence_spans`, which computes them against a
*protected* copy where dots that are not sentence boundaries have been
substituted out.

Two defects made those offsets wrong, and the second one made them wrong often.

The sentinel was `"<ABBR>"` -- six characters replacing one -- beside a comment
asserting that "protection never shifts a position". Every dot protected in a
sentence pushed everything after it five characters to the right.

And the abbreviations were matched as bare substrings, so `"p."` matched inside
"setup.", `"ed."` inside "used." / "based." / "updated." / "required.", and
`"no."` inside "casino.". Those are ordinary English sentence endings, so a
protection intended for "Dr." and "e.g." fired on a large share of English
answers. The same loop tried only `abbr` and `abbr.upper()`, so the ordinary
capitalisation -- "Dr." -- was the one form it did *not* protect.

Measured on the answer below, the hedge landed five characters into the final
sentence:

    'Access is based. The retention window is ninety days. Backups run nightly.'
    'Access is based. The retention window is ninety days. Backu基于当前可用证据，Backups run nightly.'

This reached the reader: `apply_sentence_grounding` runs from
`app/orchestration/finalization.py` on the live answer path. It is the failure
CLAUDE.md already described for URLs -- "the hedge spliced into the middle of the
link, which breaks the citation the sentence was carrying" -- happening to
ordinary prose, because the same substitution was doing it.
"""

from __future__ import annotations

import pytest

from app.services.retrieval.citation_grounding import (
    _ABBR_DOT,
    _sentence_spans,
    apply_sentence_grounding,
)

_TRAP_WORDS = [
    pytest.param("The policy was updated. Backups run nightly.", id="ed"),
    pytest.param("Access is based. Retention is ninety days.", id="based"),
    pytest.param("Setup is required. Contact the administrator.", id="required"),
    pytest.param("Configure the setup. Retention is ninety days.", id="p"),
    pytest.param("We visited the casino. Backups run nightly.", id="no"),
    pytest.param("See https://example.com/a for details. Retention is ninety days.", id="url"),
]


def test_the_sentinel_is_one_character():
    """The invariant every offset in this module rests on. It was six."""

    assert len(_ABBR_DOT) == 1


@pytest.mark.parametrize("answer", _TRAP_WORDS)
def test_every_span_lies_inside_the_answer(answer: str):
    """The assertion that would have caught it, and the cheapest one available.

    An end offset past the end of the string cannot be right, and the splice
    silently truncates rather than raising -- which is why nothing noticed.
    """

    for start, end, _sentence in _sentence_spans(answer):
        assert 0 <= start <= end <= len(answer), f"span ({start}, {end}) is outside a {len(answer)}-character answer"


@pytest.mark.parametrize("answer", _TRAP_WORDS)
def test_a_word_that_merely_ends_in_an_abbreviation_still_ends_the_sentence(answer: str):
    """ "based." is not "ed.". Each of these is two sentences; each was one, so
    the whole thing was scored as a single claim."""

    assert len(_sentence_spans(answer)) == 2


def test_a_hedge_is_not_spliced_into_the_middle_of_a_word():
    """The reader-visible failure, asserted on the exact answer that produced it."""

    answer = "Access is based. The retention window is ninety days. Backups run nightly."

    grounded, _report = apply_sentence_grounding(answer, ["Access is based on role."])

    assert "Backu基于" not in grounded, "the hedge was spliced inside the word 'Backups'"
    for sentence in ("Access is based.", "The retention window is ninety days.", "Backups run nightly."):
        assert sentence in grounded, f"{sentence!r} did not survive the splice intact"


@pytest.mark.parametrize(
    "answer",
    [
        pytest.param("Dr. Chen approved it. Backups run nightly.", id="title-case"),
        pytest.param("dr. chen approved it. Backups run nightly.", id="lower-case"),
        pytest.param("See e.g. the appendix. Backups run nightly.", id="internal-dots"),
        pytest.param("See https://example.com/a for details. Backups run nightly.", id="url"),
    ],
)
def test_a_real_abbreviation_still_suppresses_the_split(answer: str):
    """The positive direction, so the fix cannot be "stop protecting anything".

    Title case is included deliberately: the old loop tried the lower and upper
    forms only, so "Dr." -- the way anyone actually writes it -- was the single
    case it missed.
    """

    assert len(_sentence_spans(answer)) == 2


def test_a_protected_dot_comes_back_as_a_dot():
    """The sentinel is an implementation detail of the split and must never
    reach the reader."""

    spans = _sentence_spans("See e.g. the appendix. Backups run nightly.")

    assert "e.g." in spans[0][2]
    assert not any(_ABBR_DOT in sentence for _s, _e, sentence in spans)
