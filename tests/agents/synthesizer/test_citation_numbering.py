"""The reader-facing citation numbering, pinned.

The answer the model writes carries internal `[E{k}]` markers that index the
evidence list. What reaches the user is `[1]`, `[2]`, numbered by first
appearance, plus a reference list where entry n is what `[n]` points at. These
tests pin the properties that make that mapping trustworthy: no gaps, no
duplicate-looking entries, and no marker that resolves to nothing.
"""

from __future__ import annotations

from app.agents.synthesizer.citations import (
    number_evidence_markers,
    reference_label,
    render_reference_list,
)
from app.domain.contracts import EvidenceItem


def _item(
    source: str,
    page: int | None = None,
    *,
    content: str = "excerpt",
    document_id: str = "doc-1",
    version: int | None = 1,
    layer: str = "evidence",
) -> EvidenceItem:
    return EvidenceItem(
        content=content,
        source=source,
        document_id=document_id,
        version=version,
        page=page,
        layer=layer,
        retriever="vector",
    )


def test_numbers_follow_first_appearance_not_retrieval_order():
    first, second = _item("a.pdf", 1), _item("b.pdf", 2)

    text, references = number_evidence_markers("Claim [E2]. Other claim [E1].", (first, second))

    assert text == "Claim [1]. Other claim [2]."
    assert references == (second, first)


def test_a_repeated_marker_keeps_one_number_and_one_entry():
    only = _item("a.pdf", 1)

    text, references = number_evidence_markers("First [E1]. Again [E1].", (only,))

    assert text == "First [1]. Again [1]."
    assert references == (only,)


def test_excerpts_a_reader_cannot_tell_apart_share_a_number():
    """Two chunks of the same page render as one identical line; numbering them
    separately would show `[1]` and `[2]` pointing at visibly the same source."""
    first = _item("report.pdf", 3, content="first chunk")
    second = _item("report.pdf", 3, content="second chunk")

    text, references = number_evidence_markers("A [E1] and B [E2].", (first, second))

    assert text == "A [1] and B [1]."
    assert references == (first,)


def test_different_pages_of_one_document_stay_distinct():
    first, second = _item("report.pdf", 3), _item("report.pdf", 9)

    text, references = number_evidence_markers("A [E1] and B [E2].", (first, second))

    assert text == "A [1] and B [2]."
    assert references == (first, second)


def test_a_dropped_citation_takes_its_marker_with_it():
    kept, dropped = _item("a.pdf", 1), _item("secret.pdf", 2)

    text, references = number_evidence_markers(
        "Allowed [E1]. Filtered [E2]. Allowed again [E1].",
        (kept, dropped),
        keep_item_ids={kept.item_id},
    )

    assert text == "Allowed [1]. Filtered. Allowed again [1]."
    assert references == (kept,)


def test_an_out_of_range_marker_is_removed_rather_than_left_dangling():
    only = _item("a.pdf", 1)

    text, references = number_evidence_markers("Real [E1]. Invented [E7].", (only,))

    assert text == "Real [1]. Invented."
    assert references == (only,)


def test_numbering_an_answer_with_no_markers_produces_no_references():
    text, references = number_evidence_markers("No citations here.", (_item("a.pdf", 1),))

    assert text == "No citations here."
    assert references == ()


def test_local_evidence_is_named_by_filename_not_storage_path():
    item = _item("data/docs/tenant-7/user-3/quarterly report.pdf", 12)

    assert reference_label(item, "zh") == "quarterly report.pdf · 第 12 页"
    assert reference_label(item, "en") == "quarterly report.pdf · p. 12"


def test_web_evidence_keeps_the_url_that_identifies_it():
    item = _item("https://example.com/a/b?q=1", layer="web", version=None)

    assert reference_label(item, "en") == "https://example.com/a/b?q=1"


def test_a_source_without_a_page_renders_without_one():
    assert reference_label(_item("notes.md"), "zh") == "notes.md"


def test_reference_list_is_a_markdown_list_so_entries_do_not_collapse():
    """The client renders answers without remark-breaks: plain newlines would
    put every entry on one line."""
    rendered = render_reference_list((_item("a.pdf", 1), _item("b.pdf", 2)), "zh")

    assert rendered == "**参考来源**\n\n- [1] a.pdf · 第 1 页\n- [2] b.pdf · 第 2 页"


def test_reference_list_follows_the_answer_language():
    rendered = render_reference_list((_item("a.pdf", 1),), "en")

    assert rendered.startswith("**References**")
    assert "- [1] a.pdf · p. 1" in rendered


def test_no_references_renders_nothing_to_append():
    assert render_reference_list((), "zh") == ""
