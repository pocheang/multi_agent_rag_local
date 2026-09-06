"""Heading detection, and the blank line that used to raise.

`detect_heading_level` reads `line[0]` in its title-case rule, so asking it about
an empty line was an `IndexError` -- and `extract_document_structure` calls it on
*every* line before checking whether the line is blank. Any document containing a
blank line therefore blew up the structure pass, which is nearly all of them.

That was latent rather than shipping, for a reason worth keeping written down:
`PDF_ENABLE_STRUCTURE_ANALYSIS` defaults false. With it on, the failure would not
have looked like a crash either -- `load_pdf_advanced` catches per page and keeps
the *original* document, so formula enrichment and coreference resolution would
have been discarded along with the structure, and all three switches would have
looked like features that simply did nothing.

The rest pins what a heading is, since `splitter._heading_scope` now labels every
chunk with one and a change here changes what gets stored on ingest.
"""

from __future__ import annotations

import pytest

from app.ingestion.processing.structure import (
    add_section_metadata,
    detect_heading_level,
    extract_document_structure,
    section_headings,
)


@pytest.mark.parametrize("blank", ["", "   ", "\t", "\n", "  \t \n "])
def test_a_blank_line_is_not_a_heading_and_does_not_raise(blank):
    assert detect_heading_level(blank) is None


def test_structure_analysis_survives_a_document_with_blank_lines():
    text = "# Title\n\nA paragraph with a blank line above it.\n\n## Section\n\nMore text.\n"

    sections = extract_document_structure(text)

    assert [(s.level, s.title) for s in sections] == [(1, "Title"), (2, "Section")]
    # The caller's next step must work on the result too.
    assert "Document Structure" in add_section_metadata(text, sections)


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("# Title", 1),
        ("## Backup retention policy", 2),
        ("###### Deep", 6),
        ("####### Too deep", None),
        ("#", None),
        ("# ", None),
        ("1. Scope", 1),
        ("1.2.3. Scope", 3),
        # The numbering must end in a dot: `(\d+\.)+\s+[A-Z]` finds no whitespace
        # after "1.2." because "3" follows it, so this is not a numbered heading.
        ("1.2.3 Scope", None),
        ("ALL CAPS HEADING", 1),
        ("AB", None),
        ("Title Case Heading", 2),
        ("This is ordinary prose that ends in a full stop.", None),
        ("- a bullet item", None),
    ],
)
def test_each_rule_answers_for_its_own_shape(line, expected):
    assert detect_heading_level(line) == expected


def test_the_rules_are_tried_in_order():
    # "1. SCOPE" satisfies both the numbered rule and the all-caps one; numbered
    # wins because it comes first, and it reports depth rather than level 1.
    assert detect_heading_level("1. SCOPE") == 1
    assert detect_heading_level("1.2. SCOPE") == 2


def test_section_headings_returns_them_in_document_order():
    text = "# One\n\nbody text here.\n\n## Two\n\nmore body.\n\n## Three\n"

    assert section_headings(text) == ["# One", "## Two", "## Three"]
    assert section_headings("no headings at all, just a sentence.") == []
    assert section_headings("") == []


def test_a_chinese_heading_is_not_detected():
    """A known limit, recorded rather than implied.

    Every rule is written for Latin script: markdown still works, but a bare
    Chinese section title matches none of them, so a Chinese document without `#`
    markers gets no headings on its chunks. This system is bilingual and this part
    is not.
    """
    assert detect_heading_level("备份保留策略") is None
    assert detect_heading_level("## 备份保留策略") == 2
