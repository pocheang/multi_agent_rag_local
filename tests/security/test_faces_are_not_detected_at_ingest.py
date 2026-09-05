"""This system does not look for faces in a user's image.

`app/ingestion/extraction/people.py` ran OpenCV face and HOG detection over every
ingested image and produced five fields -- `human_present`, `person_count`,
`face_count`, `person_detection_status`, `person_detector_mode`. It was on by
default, so nobody chose it, and `build_people_summary` rendered three of them
into the same `page_content` as the OCR text: for a standalone uploaded image
that string *is* the chunk, indexed into the main corpus through both vector and
BM25. `5e87234e` turned it off and stopped the summary reaching content.

It is deleted now (2026-09-05), because the remaining question had no good
answer. Nothing in `app/` or the frontend read any of the five fields, and by
this repository's own rule a producer with no consumer is deleted rather than
configured -- a switch over something nothing reads is not configurability. The
only consumer anyone could name for a face count is itself a privacy inference,
which is a proposal, not a restoration.

Two details worth keeping: OpenCV was never a declared dependency, so on most
installations `detect_people_in_image` caught `ImportError` and reported
"unavailable" -- the detection ran only where something else had pulled cv2 in,
which is the worst version of a privacy-affecting default. And CLAUDE.md's
"still not covered" list, which exists to say what the redaction layer does and
does not reach, never mentioned it.

So these are negative assertions on purpose. They fail if the subsystem comes
back, under this name or another.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.core.config import Settings

APP = Path("app")

# The library calls that constitute face/person detection, whatever the module
# around them is called. Matching the API rather than the old module name is the
# point: a reimplementation under a different name is the thing to catch.
_DETECTOR_CALLS = re.compile(
    r"CascadeClassifier|HOGDescriptor|haarcascade|detectMultiScale|face_recognition|mediapipe",
)

# The fields it produced. `person_count` alone would over-match ordinary prose,
# so these are matched as dictionary keys and attribute names.
_PRODUCED_FIELDS = re.compile(
    r"""["']?\b(human_present|person_count|face_count|person_detector_mode|person_detection_status)\b["']?""",
)


def _python_sources() -> list[tuple[Path, str]]:
    return [(p, p.read_text(encoding="utf-8")) for p in APP.rglob("*.py")]


def test_nothing_runs_a_face_or_person_detector():
    """The assertion that matters. It is about the capability, not the module."""

    offenders = [str(path) for path, src in _python_sources() if _DETECTOR_CALLS.search(src)]

    assert not offenders, f"face/person detection reappeared in: {offenders}"


def test_no_module_produces_the_fields_it_produced():
    """A detector wired to a different metadata vocabulary would pass the check
    above. These five names are what actually reached the index."""

    offenders = [str(path) for path, src in _python_sources() if _PRODUCED_FIELDS.search(src)]

    assert not offenders, f"people-detection fields reappeared in: {offenders}"


def test_the_settings_are_gone_rather_than_defaulted_off():
    """Off-by-default was the previous state and it was not enough: the field
    invited an operator to switch on something nothing reads."""

    fields = set(Settings.model_fields)

    assert "people_detection_enabled" not in fields
    assert "people_detection_mode" not in fields


def test_the_image_path_still_works_without_it():
    """Guards that the deletion removed the detector and not the ingest path it
    sat inside -- the same shape as
    `tests/orchestration/test_clarification_is_not_a_pipeline_stage.py`."""

    from app.ingestion.extraction.ocr import ocr_image_bytes
    from app.ingestion.utils import build_vision_summary, describe_image_with_vision

    assert callable(ocr_image_bytes)
    assert callable(build_vision_summary)
    assert callable(describe_image_with_vision)


def test_the_compatibility_export_surfaces_do_not_advertise_it():
    """`app/ingestion/loaders/` and `app/ingestion/utils/` re-export by name for
    historical importers, and a name in `__all__` that no longer resolves fails
    only when somebody touches it."""

    from app.ingestion import loaders, utils

    for module in (loaders, utils):
        for name in module.__all__:
            assert getattr(module, name, None) is not None, f"{module.__name__}.{name} does not resolve"
        assert not any("people" in name for name in module.__all__)
