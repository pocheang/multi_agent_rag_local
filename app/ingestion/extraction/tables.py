"""Cross-page table detection and merging."""

import re

_SEPARATOR_ROW_RE = re.compile(r"^\|[\s\-:]+\|")
"""The row under a markdown table header.

Named on 2026-09-05 because three call sites had to agree on it. Two of them,
`is_table_start` and `extract_table_header`, were deleted the next day together
with `merge_table_pages`, their only caller -- so one asks it today. Still named
and compiled once: `is_table_continuation` is defined by what it excludes, and a
bare pattern there would say less than the name does."""


def is_table_continuation(text: str) -> bool:
    """Check if text looks like table continuation (no header).

    Args:
        text: Text content

    Returns:
        True if looks like table continuation
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if not lines:
        return False

    # Check if first few lines have consistent pipe structure
    pipe_lines = [line for line in lines[:5] if "|" in line]
    if len(pipe_lines) < 2:
        return False

    # Check consistent column count
    pipe_counts = [line.count("|") for line in pipe_lines]
    if len(set(pipe_counts)) == 1 and pipe_counts[0] >= 2:
        # Make sure it's NOT a header (no separator line)
        if len(lines) > 1 and not _SEPARATOR_ROW_RE.match(lines[1]):
            return True

    return False


def detect_incomplete_table(text: str) -> bool:
    """Detect if page ends with an incomplete table.

    Args:
        text: Page text content

    Returns:
        True if page likely ends with incomplete table
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) < 3:
        return False

    # Check last few lines
    last_lines = lines[-5:]
    table_lines = [line for line in last_lines if "|" in line]

    # If more than half of last lines are table rows, likely incomplete
    if len(table_lines) >= len(last_lines) // 2 and len(table_lines) >= 2:
        # Check if there's no clear table end marker
        last_line = lines[-1]
        # Table usually ends with empty line or non-table content
        if "|" in last_line:
            return True

    return False


def merge_cross_page_tables(pages_content: list[str]) -> list[str]:
    """Main function to merge tables across pages.

    Args:
        pages_content: List of page content (Markdown format)

    Returns:
        List of pages with cross-page tables merged
    """
    if len(pages_content) < 2:
        return pages_content

    merged = []
    i = 0

    while i < len(pages_content):
        current = pages_content[i]

        # Check if current page has incomplete table at end
        if detect_incomplete_table(current) and i + 1 < len(pages_content):
            next_page = pages_content[i + 1]

            # Check if next page starts with table continuation
            if is_table_continuation(next_page):
                # Merge the two pages
                merged.append(current + "\n" + next_page)
                i += 2
                continue

        merged.append(current)
        i += 1

    return merged
