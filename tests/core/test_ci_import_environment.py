"""The CI-simulation plugin must describe CI, not an invented environment.

`scripts/ci_import_environment.py` exists because a test can silently depend on
an optional package the developer has and CI does not. That failure is only
visible after a push, which is the worst place to find it -- and it happened:
`test_present_tesseract_is_active` patched `shutil.which` while `_ocr` imports
pytesseract first, so it asserted the positive direction only on a machine that
had the package.

A simulation is itself a claim, and a wrong one is worse than none -- it sends
you to fix code that is not broken. So this checks both directions of the claim:
nothing in the blocked set is actually installed by CI, and the set is not empty.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path("scripts").resolve()))

from ci_import_environment import BLOCKED_IMPORTS, REQUIREMENTS  # noqa: E402

# import name -> the distribution that would provide it, where they differ.
_DISTRIBUTION_NAMES = {
    "cv2": "opencv-python",
    "fitz": "pymupdf",
    "sentence_transformers": "sentence-transformers",
}


def _pinned_distributions() -> set[str]:
    """Every distribution `pip install -r requirements/ci.txt` would install."""

    text = REQUIREMENTS.read_text(encoding="utf-8")
    return {match.group(1).lower().replace("_", "-") for match in re.finditer(r"^([A-Za-z0-9._-]+)==", text, re.M)}


def test_the_blocked_set_is_not_empty():
    """A blocker that blocks nothing runs the suite exactly as before and reports
    success -- the same shape as a scanner whose patterns match nothing."""

    assert BLOCKED_IMPORTS


def test_every_entry_carries_a_reason():
    """A bare list would not survive its author. Each entry says why CI lacks it."""

    for name, reason in BLOCKED_IMPORTS.items():
        assert reason.strip(), f"{name} is blocked with no reason given"


@pytest.mark.parametrize("import_name", sorted(BLOCKED_IMPORTS))
def test_nothing_blocked_is_actually_installed_by_ci(import_name: str):
    """The direction that makes this a simulation rather than a fiction.

    Blocking something CI *does* install would fail tests that CI passes, and
    send whoever is holding the red build to change working code.
    """

    distribution = _DISTRIBUTION_NAMES.get(import_name, import_name).replace("_", "-")

    assert distribution not in _pinned_distributions(), (
        f"{import_name} is blocked but requirements/ci.txt pins {distribution}; CI has it"
    )


def test_the_requirements_file_was_actually_read():
    """Otherwise the assertion above passes against an empty set, for a path
    typo, and would keep passing forever."""

    assert len(_pinned_distributions()) > 50
