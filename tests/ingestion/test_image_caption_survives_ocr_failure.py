"""A described image must stay indexable when OCR cannot read it.

`ocr_image_bytes` renders the scene caption, the people summary and the OCR
result into one `page_content`, and marks a failed OCR with `[image_ocr_error]`.
`_readable_image_text` then discarded the whole string whenever that marker
appeared -- for a good reason, stated in `_index_images`: indexing "Tesseract
executable not found" would make the diagnostic itself retrievable, which is
worse than the image being absent.

The cost was not noticed. The vision caption sits in that same string, so it went
with the diagnostic -- and it went precisely in the case a vision model exists
for: a photo, a diagram, a chart with no extractable text. With
IMAGE_CAPTION_ENABLED on and Tesseract missing, the model produced a perfect
description and the image was indexed as nothing at all.

The caption is also carried on its own in `metadata["image_caption"]`, which
never holds a diagnostic. Reading it from there keeps both properties: the image
is searchable, and the error message still is not.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from app.services.documents.ingest import _readable_image_text

_CAPTION = "A bar chart comparing quarterly revenue across four regions."
_OCR_TEXT = "Q1 120 Q2 150 Q3 180 Q4 210"
_DIAGNOSTIC = "Tesseract executable not found"


def _image() -> SimpleNamespace:
    """An image the loader could not read anything out of, so OCR is attempted."""

    return SimpleNamespace(description="", ocr_text="", data=b"fake-bytes", image_id="img-1", page=1)


def _document(page_content: str, caption: str = "") -> SimpleNamespace:
    metadata = {"image_caption": caption} if caption else {}
    return SimpleNamespace(page_content=page_content, metadata=metadata)


def _ocr_failed(*_args, **_kwargs):
    return [
        _document(
            f"[image] one image\n[people] none\n[image_scene] status=ok; model=gpt\n{_CAPTION}\n"
            f"[image_ocr_error]\n{_DIAGNOSTIC}",
            caption=_CAPTION,
        )
    ]


def _ocr_succeeded(*_args, **_kwargs):
    return [
        _document(
            f"[image] one image\n[people] none\n[image_scene] status=ok; model=gpt\n{_CAPTION}\n"
            f"[image_ocr]\n{_OCR_TEXT}",
            caption=_CAPTION,
        )
    ]


def _ocr_failed_without_vision(*_args, **_kwargs):
    return [_document(f"[image] one image\n[image_ocr_error]\n{_DIAGNOSTIC}")]


def test_a_caption_survives_a_failed_ocr():
    """The assertion that would have caught it: this returned "" before."""

    text = _readable_image_text(_image(), _ocr_failed, Path("photo.png"))

    assert _CAPTION in text


def test_the_diagnostic_is_still_never_indexed():
    """The property the discard existed to protect, which the fix must not lose.

    "Tesseract executable not found" as retrievable evidence is worse than the
    image being absent.
    """

    text = _readable_image_text(_image(), _ocr_failed, Path("photo.png"))

    assert _DIAGNOSTIC not in text
    assert "[image_ocr_error]" not in text


def test_an_image_with_neither_ocr_nor_caption_is_still_skipped():
    """Without a caption there is nothing readable, so the image stays absent --
    `_index_images` skips on an empty string."""

    assert _readable_image_text(_image(), _ocr_failed_without_vision, Path("photo.png")) == ""


def test_a_successful_ocr_keeps_the_whole_rendered_block():
    text = _readable_image_text(_image(), _ocr_succeeded, Path("scan.png"))

    assert _OCR_TEXT in text
    assert _CAPTION in text


def test_a_caption_is_not_indexed_twice_when_ocr_succeeded():
    """It is in the rendered block and in metadata; counting it once keeps the
    excerpt honest and stops it outweighing the OCR text during retrieval."""

    text = _readable_image_text(_image(), _ocr_succeeded, Path("scan.png"))

    assert text.count(_CAPTION) == 1


def test_a_loader_that_already_read_the_image_is_left_alone():
    """OCR is only attempted when the loader produced nothing; that path is
    unchanged."""

    image = SimpleNamespace(
        description="Loader description",
        ocr_text="",
        data=b"fake-bytes",
        image_id="img-1",
        page=1,
    )

    def _must_not_run(*_args, **_kwargs):  # pragma: no cover - asserted by absence
        raise AssertionError("OCR must not be attempted when the loader already read the image")

    assert _readable_image_text(image, _must_not_run, Path("photo.png")) == "Loader description"
