"""Cross-page table detection and merging."""

import re


def is_table_start(text: str) -> bool:
    """Check if text looks like the start of a table.

    Args:
        text: Text content

    Returns:
        True if looks like table start
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) < 2:
        return False

    # Check for Markdown table header
    if "|" in lines[0] and "|" in lines[1]:
        # Check if second line is separator (|---|---|)
        if re.match(r"^\|[\s\-:]+\|", lines[1]):
            return True

    # Check for consistent column structure
    pipe_counts = [line.count("|") for line in lines[:3]]
    if len(set(pipe_counts)) == 1 and pipe_counts[0] >= 2:
        return True

    return False


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
        if len(lines) > 1 and not re.match(r"^\|[\s\-:]+\|", lines[1]):
            return True

    return False


def extract_table_header(text: str) -> tuple[str, str]:
    """Extract table header from text.

    Args:
        text: Text containing table

    Returns:
        Tuple of (header_text, remaining_text)
    """
    lines = text.split("\n")
    header_lines = []

    for i, line in enumerate(lines):
        if "|" in line:
            header_lines.append(line)
            # Check if next line is separator
            if i + 1 < len(lines) and re.match(r"^\|[\s\-:]+\|", lines[i + 1].strip()):
                header_lines.append(lines[i + 1])
                remaining = "\n".join(lines[i + 2 :])
                return "\n".join(header_lines), remaining
        elif header_lines:
            # No more header lines
            break

    return "", text


def merge_table_pages(pages: list[str]) -> list[str]:
    """Merge tables that span across multiple pages.

    Args:
        pages: List of page content (Markdown format)

    Returns:
        List of pages with merged tables
    """
    if len(pages) < 2:
        return pages

    merged_pages = []
    i = 0

    while i < len(pages):
        current_page = pages[i]

        # Check if current page ends with a table
        if is_table_start(current_page) or "|" in current_page:
            # Check if next page continues the table
            if i + 1 < len(pages):
                next_page = pages[i + 1]

                if is_table_continuation(next_page):
                    # Merge tables
                    # Extract header from current page
                    header, current_body = extract_table_header(current_page)

                    # Get continuation rows from next page
                    next_lines = [line for line in next_page.split("\n") if "|" in line]

                    # Combine
                    if header:
                        merged = current_page + "\n" + "\n".join(next_lines)
                    else:
                        merged = current_page + "\n" + next_page

                    merged_pages.append(merged)
                    i += 2  # Skip next page as it's merged
                    continue

        # No merge needed
        merged_pages.append(current_page)
        i += 1

    return merged_pages


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
