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


def detect_heading_level(line: str) -> int | None:
    """
    Detect if line is a heading and return its level.

    Args:
        line: Text line

    Returns:
        Heading level (1-6) or None
    """
    line = line.strip()

    # Markdown headings
    if line.startswith("#"):
        level = 0
        for char in line:
            if char == "#":
                level += 1
            else:
                break
        if level <= 6 and line[level:].strip():
            return level

    # Numbered headings (1., 1.1, 1.1.1, etc.)
    numbered_pattern = r"^(\d+\.)+\s+[A-Z]"
    if re.match(numbered_pattern, line):
        dots = line.split()[0].count(".")
        return min(dots, 6)

    # All caps short lines (likely headings)
    if line.isupper() and 5 <= len(line) <= 100:
        return 1

    # Title case with no punctuation at end
    if line[0].isupper() and not line.endswith((".", "!", "?", ",")):
        words = line.split()
        if 2 <= len(words) <= 15:
            # Check if most words are capitalized
            capitalized = sum(1 for w in words if w[0].isupper())
            if capitalized / len(words) > 0.6:
                return 2

    return None


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
