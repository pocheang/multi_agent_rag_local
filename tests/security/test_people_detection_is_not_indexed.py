"""Face counts derived from a user's image must not become searchable text.

`detect_people_in_image` runs OpenCV face/HOG detection over every ingested
image. `build_people_summary` rendered the result -- `human_present`,
`person_count`, `face_count` -- into the same `page_content` as the OCR text, and
for a standalone uploaded image that string *is* the chunk: indexed into the main
corpus, vector and BM25 both.

Three things made that worse than it sounds. It was on by default, so no one
chose it. Nothing anywhere in `app/` or the frontend reads any of the five fields
it produces, so the exposure bought nothing. And CLAUDE.md, which enumerates what
the redaction layer does and does not cover, never mentioned it.

So: detection is opt-in now, and its output never reaches the indexed text. The
metadata keys are left in place -- removing the subsystem outright is a product
decision, not a defect fix, and it is recorded as a follow-up.
"""

from __future__ import annotations

from app.core.config import Settings
from app.ingestion.extraction.people import build_people_summary, detect_people_in_image


class _Unconvertible:
    """Stands in for a PIL image. Detection never gets far enough to use it."""

    def convert(self, _mode: str):  # pragma: no cover - not reached when disabled
        raise AssertionError("people detection must not run when it is switched off")


def test_people_detection_is_off_by_default():
    """A privacy-affecting feature should not be opt-out. It was."""

    assert Settings().people_detection_enabled is False


def test_a_disabled_detector_does_not_touch_the_image():
    """Off means it does not run, not that it runs and discards the result."""

    result = detect_people_in_image(_Unconvertible(), Settings())

    assert result["status"] == "disabled"
    assert result["person_count"] == 0
    assert result["human_present"] is False


def test_the_missing_setting_defaults_to_off_too():
    """`detect_people_in_image` reads the flag with a getattr default, which used
    to be True -- so an object without the attribute switched detection *on*."""

    class _NoSuchSetting:
        pass

    assert detect_people_in_image(_Unconvertible(), _NoSuchSetting())["status"] == "disabled"


def test_the_people_summary_never_reaches_indexed_content():
    """The assertion that would have caught it.

    Both OCR paths composed `f"{summary}\\n{people_summary}\\n{vision_summary}..."`,
    and for an uploaded image that content is the chunk text.
    """

    from pathlib import Path

    sources = [
        Path("app/ingestion/extraction/ocr.py").read_text(encoding="utf-8"),
        Path("app/ingestion/extraction/ocr_enhanced.py").read_text(encoding="utf-8"),
    ]

    for source in sources:
        composed = [line for line in source.splitlines() if "content = f" in line or "content = (" in line]
        assert composed, "the content composition moved; this test needs updating rather than deleting"
        assert not any("people_summary" in line for line in composed)


def test_the_summary_helper_still_reports_what_it_is_given():
    """Kept deliberately. The helper is not the defect -- publishing its output
    into a search index was -- and a caller that wants it for a diagnostic should
    still get an honest answer."""

    summary = build_people_summary({"status": "ok", "human_present": True, "person_count": 2, "face_count": 2})

    assert "person_count=2" in summary
