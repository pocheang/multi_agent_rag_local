"""Run the suite with the packages CI does not install made unimportable.

    pytest tests/ -q -p ci_import_environment      # with scripts/ on PYTHONPATH
    make test-ci                                    # the same thing, spelled once

A development machine accumulates optional packages -- pytesseract, pdfplumber,
sentence-transformers -- that `requirements/ci.txt` does not contain, and a test
that touches one inherits it silently. `test_present_tesseract_is_active` did
exactly that: it patched `shutil.which` to simulate the binary being present,
while `_ocr` imports pytesseract *first*, so the assertion only held on a machine
that happened to have the package. Green locally, red in CI, and only visible
after a push.

Blocking happens at the `sys.meta_path` finder, not by replacing `__import__`.
That distinction matters: a genuinely absent package is still satisfied from
`sys.modules`, so a test that injects a fake there must keep working. The first
version of this replaced `__import__` and reported a failure in
`test_a_missing_model_never_reaches_the_network` that CI does not have -- a
simulation that is stricter than the thing it simulates sends you to fix code
that is not broken.

The blocked set is checked against `requirements/ci.txt` by
`tests/core/test_ci_import_environment.py`, so an entry that CI actually installs
fails rather than quietly over-restricting the run.
"""

from __future__ import annotations

import sys
from importlib.abc import MetaPathFinder
from pathlib import Path

# Import names, not distribution names -- this is what `import x` looks for.
# Each must be absent from requirements/ci.txt; the test above enforces it.
BLOCKED_IMPORTS: dict[str, str] = {
    "pytesseract": "OCR is optional; CI never reads text out of an image.",
    "cv2": "OpenCV was never a declared dependency at all.",
    "fitz": "PyMuPDF is the optional `multimodal` extra.",
    "pdfplumber": "PDF table extraction is optional.",
    "paddleocr": "The alternative OCR engine is optional.",
    "docling": "The advanced PDF loader is optional.",
    "sentence_transformers": "The reranker and NLI cross-encoder load from local files or not at all.",
}

REQUIREMENTS = Path(__file__).resolve().parents[1] / "requirements" / "ci.txt"


class _NotInstalled(MetaPathFinder):
    """Make one set of packages look absent, whatever is on disk."""

    def find_spec(self, fullname, path=None, target=None):  # noqa: D102 - MetaPathFinder protocol
        root = fullname.split(".", 1)[0]
        if root in BLOCKED_IMPORTS:
            raise ModuleNotFoundError(
                f"No module named {fullname!r} (blocked by scripts/ci_import_environment.py: {BLOCKED_IMPORTS[root]})",
                name=fullname,
            )
        return None


def pytest_configure(config) -> None:  # noqa: ARG001 - pytest plugin hook signature
    """Installed as a pytest plugin via `-p ci_import_environment`.

    Anything already imported is dropped first: pytest's own start-up may have
    pulled one of these in, and a finder only affects imports that have not
    happened yet.

    The line it prints is not decoration. A plugin that silently did nothing --
    a typo in `-p`, a renamed file -- would leave the run looking like a
    CI simulation while being an ordinary one, which is the failure this whole
    file exists to prevent.
    """

    for name in list(sys.modules):
        if name.split(".", 1)[0] in BLOCKED_IMPORTS:
            del sys.modules[name]
    sys.meta_path.insert(0, _NotInstalled())
    print(f"ci_import_environment: {len(BLOCKED_IMPORTS)} packages hidden to match requirements/ci.txt")
