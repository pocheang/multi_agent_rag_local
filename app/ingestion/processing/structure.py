"""Document structure analysis - detect chapters, sections, and hierarchies."""

import re
from dataclasses import dataclass
from typing import Optional


@dataclass
class DocumentSection:
    """Represents a section in the document."""

    level: int  # 1=chapter, 2=section, 3=subsection, etc.
    title: str
    content: str
    page: int | None = None
    parent: Optional["DocumentSection"] = None
    children: list["DocumentSection"] = None

    def __post_init__(self):
        if self.children is None:
            self.children = []


_NUMBERED_HEADING_RE = re.compile(r"^(\d+\.)+\s+[A-Z]")


def _markdown_heading(line: str) -> int | None:
    """`## Title`. Seven or more hashes is not a heading, nor are hashes alone."""
    if not line.startswith("#"):
        return None
    level = len(line) - len(line.lstrip("#"))
    if level <= 6 and line[level:].strip():
        return level
    return None


def _numbered_heading(line: str) -> int | None:
    """`1. Scope`, `1.2.3 Scope`. The level is how deep the numbering goes."""
    if not _NUMBERED_HEADING_RE.match(line):
        return None
    return min(line.split()[0].count("."), 6)


def _all_caps_heading(line: str) -> int | None:
    """A short shouted line. Long ones are prose that happens to be shouted."""
    return 1 if line.isupper() and 5 <= len(line) <= 100 else None


def _title_case_heading(line: str) -> int | None:
    """Mostly-capitalised words with no sentence-ending punctuation.

    The loosest of the four, and the one that costs the false positives measured
    in `section_headings`. Ordinary prose escapes it by ending in a full stop.
    """
    if not line[0].isupper() or line.endswith((".", "!", "?", ",")):
        return None
    words = line.split()
    if not 2 <= len(words) <= 15:
        return None
    capitalized = sum(1 for word in words if word[0].isupper())
    return 2 if capitalized / len(words) > 0.6 else None


# Order is load-bearing: the first rule that recognises the line wins, and the
# rules overlap. "1. SCOPE" is a numbered heading rather than an all-caps one.
_HEADING_RULES = (_markdown_heading, _numbered_heading, _all_caps_heading, _title_case_heading)


def detect_heading_level(line: str) -> int | None:
    """
    Detect if line is a heading and return its level.

    Args:
        line: Text line

    Returns:
        Heading level (1-6) or None
    """
    line = line.strip()

    # A blank line is not a heading, and asking used to raise: the title-case rule
    # reads `line[0]` after stripping, so `detect_heading_level("")` was an
    # IndexError. `extract_document_structure` calls this on *every* line before it
    # checks whether the line is blank, so it raised on any document containing one
    # -- which is nearly all of them. That was latent rather than shipping only
    # because PDF_ENABLE_STRUCTURE_ANALYSIS defaults false; with it on, the caller's
    # per-page `except Exception` kept the original document, so formula enrichment
    # and coreference resolution were discarded along with the structure, and the
    # switch could not usefully be turned on.
    if not line:
        return None

    for rule in _HEADING_RULES:
        level = rule(line)
        if level is not None:
            return level

    return None


def section_headings(text: str) -> list[str]:
    """Every heading line in `text`, in document order, as written.

    One definition of "what is a heading" for the whole ingest path: the chunker
    labels chunks with this and `extract_document_structure` builds its tree from
    the same predicate, so the two cannot come to disagree.

    A heading here is a hint, not a guarantee. `detect_heading_level` is
    deliberately liberal, and measured over 415 lines of real corpus and README
    text it flagged 50 lines, 45 of them genuine markdown headings; the five it
    was wrong about were ordered-list items ("1. Write tests for new features")
    and one ASCII-diagram line that happened to be all caps. Treat a chunk's
    `heading` as "probably the section this came from", not as a key.
    """
    return [line.strip() for line in text.splitlines() if detect_heading_level(line) is not None]


def extract_document_structure(text: str, page: int | None = None) -> list[DocumentSection]:
    """
    Extract hierarchical structure from document text.

    Args:
        text: Document text
        page: Page number

    Returns:
        List of DocumentSection objects
    """
    lines = text.split("\n")
    sections = []
    current_section = None
    current_content = []

    for line in lines:
        heading_level = detect_heading_level(line)

        if heading_level:
            # Save previous section
            if current_section:
                current_section.content = "\n".join(current_content).strip()
                sections.append(current_section)

            # Start new section
            current_section = DocumentSection(level=heading_level, title=line.strip("#").strip(), content="", page=page)
            current_content = []
        else:
            # Add to current section content
            if line.strip():
                current_content.append(line)

    # Save last section
    if current_section:
        current_section.content = "\n".join(current_content).strip()
        sections.append(current_section)

    return sections


def add_section_metadata(text: str, sections: list[DocumentSection]) -> str:
    """
    Add section metadata to text for better context.

    Args:
        text: Original text
        sections: Document sections

    Returns:
        Text with section metadata
    """
    lines = []

    # Add table of contents
    lines.append("# Document Structure")
    lines.append("")
    for section in sections:
        indent = "  " * (section.level - 1)
        lines.append(f"{indent}- {section.title}")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Add original text
    lines.append(text)

    return "\n".join(lines)
