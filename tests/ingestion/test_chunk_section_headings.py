"""A chunk from the middle of a section does not know which section it is in.

`SmartChunker` (`app/services/multimodal/smart_chunker.py`, deleted in the
commit that added this file) was 483 lines aimed at exactly that gap: it split a
PDF by heading into `Section`s and carried the heading onto every chunk it made.
Nothing in `app/` ever constructed it, so none of that ran.

It was deleted rather than connected because connecting it meant rewriting the
parts that do the work. It read PDFs only, through `fitz`, where the loader
handles many formats; it had no notion of the parent/child pair the retrieval
path expands through; its `DocumentChunk` is not the type the index takes; and
`_split_section` ended with

    # For simplicity, add all to first chunk
    chunks[0].tables = section.tables

which is the *same* defect CLAUDE.md already records against the live splitter
under Multimodal retrieval -- a 40-row table cut into seven chunks, only the
first of which carries the header row.

The idea is worth keeping and the implementation was not, so the gap is recorded
here as an executable claim rather than as a sentence in a plan. When headings do
survive chunking, this test passes, `strict=True` fails the suite, and whoever
did the work removes the marker -- the pattern
`docs/superpowers/plans/2026-08-29-user-data-isolation.md` used for its eight.
"""

from __future__ import annotations

import pytest

from app.ingestion.chunking.splitter import split_documents
from app.services import multimodal

_HEADING = "## Backup retention policy"
_BODY = "Nightly snapshots are retained for thirty days before deletion. " * 40


class _Doc:
    """The shape `split_documents` reads: `page_content` plus `metadata`."""

    def __init__(self, page_content: str, metadata: dict) -> None:
        self.page_content = page_content
        self.metadata = metadata

    def model_copy(self, *, update: dict):  # pragma: no cover - exercised via _clone_document
        merged = {"page_content": self.page_content, "metadata": self.metadata, **update}
        return _Doc(merged["page_content"], merged["metadata"])


def _chunks():
    document = _Doc(f"{_HEADING}\n\n{_BODY}", {"source": "policy.md", "document_id": "d1", "version": "1"})
    children, _parents = split_documents([document])
    return children


def test_the_section_is_long_enough_to_be_split():
    """Otherwise the assertion below would hold for an uninteresting reason."""

    assert len(_chunks()) > 1


@pytest.mark.xfail(strict=True, reason="headings do not survive chunking; SmartChunker aimed at this and never ran")
def test_every_chunk_of_a_section_carries_its_heading():
    """What a reader needs and what retrieval scores against.

    Measured on the document below -- one heading and forty sentences under it,
    which the shipped 600-character child splitter cuts into seven:

        chunk 0   26 chars   "## Backup retention policy"   <- the heading, alone
        chunks 1-6           the policy text                <- no heading anywhere

    So it is worse than the heading merely not propagating. The separator list
    splits *at* the heading, which strands it in a chunk of its own with no body
    to support -- a retrievable item that answers nothing -- while the six chunks
    holding the answer carry no word saying what they are about.
    """

    for chunk in _chunks():
        assert _HEADING in chunk.page_content or _HEADING in str(chunk.metadata.get("heading", ""))


def test_the_deleted_chunker_is_not_half_deleted():
    """Every name the package advertises must resolve.

    `app/services/multimodal/__init__.py` serves its classes from `__getattr__`
    so the optional extra stays optional -- which means a stale `__all__` entry
    raises `AttributeError` at the moment somebody touches it rather than at
    import, and `from ... import *` is the only thing that would notice.
    """

    for name in multimodal.__all__:
        assert getattr(multimodal, name, None) is not None, f"{name} is advertised but does not resolve"
