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


def build_hierarchy(sections: list[DocumentSection]) -> list[DocumentSection]:
    """
    Build parent-child relationships between sections.

    Args:
        sections: Flat list of sections

    Returns:
        List of top-level sections with children
    """
    if not sections:
        return []

    root_sections = []
    stack = []  # Stack of (level, section)

    for section in sections:
        # Pop sections with higher or equal level
        while stack and stack[-1][0] >= section.level:
            stack.pop()

        # Set parent
        if stack:
            parent = stack[-1][1]
            section.parent = parent
            parent.children.append(section)
        else:
            root_sections.append(section)

        stack.append((section.level, section))

    return root_sections


def structure_to_markdown(sections: list[DocumentSection], level: int = 0) -> str:
    """
    Convert document structure to Markdown with hierarchy.

    Args:
        sections: List of sections
        level: Current indentation level

    Returns:
        Markdown text
    """
    lines = []

    for section in sections:
        # Add heading
        heading = "#" * section.level + " " + section.title
        lines.append(heading)
        lines.append("")

        # Add content
        if section.content:
            lines.append(section.content)
            lines.append("")

        # Add children recursively
        if section.children:
            child_md = structure_to_markdown(section.children, level + 1)
            lines.append(child_md)

    return "\n".join(lines)


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


def extract_references(text: str) -> list[dict[str, str]]:
    """
    Extract references and citations from text.

    Args:
        text: Document text

    Returns:
        List of reference dicts with 'id', 'text', 'type'
    """
    references = []

    # Pattern: [1], [Smith 2020], etc.
    citation_pattern = r"\[([^\]]+)\]"
    citations = re.findall(citation_pattern, text)

    for citation in citations:
        # Check if it's a reference (number or author-year)
        if citation.isdigit() or re.match(r"[A-Z][a-z]+\s+\d{4}", citation):
            references.append({"id": citation, "text": f"[{citation}]", "type": "citation"})

    # Pattern: "See Chapter 3", "as shown in Section 2.1"
    cross_ref_pattern = r"(Chapter|Section|Figure|Table)\s+(\d+\.?\d*)"
    cross_refs = re.findall(cross_ref_pattern, text, re.IGNORECASE)

    for ref_type, ref_id in cross_refs:
        references.append({"id": ref_id, "text": f"{ref_type} {ref_id}", "type": "cross_reference"})

    return references
