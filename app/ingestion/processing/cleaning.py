"""PDF content cleaning utilities - header/footer removal and noise filtering."""

from collections import Counter


def detect_repeated_patterns(pages_content: list[str], min_occurrences: int = 3) -> set[str]:
    """Detect repeated text patterns across pages (likely headers/footers).

    Args:
        pages_content: List of page text content
        min_occurrences: Minimum times a pattern must appear to be considered repeated

    Returns:
        Set of repeated text patterns to filter out
    """
    if len(pages_content) < min_occurrences:
        return set()

    # Extract first and last 3 lines from each page
    first_lines = []
    last_lines = []

    for content in pages_content:
        lines = [line.strip() for line in content.split("\n") if line.strip()]
        if len(lines) >= 3:
            first_lines.extend(lines[:3])
            last_lines.extend(lines[-3:])
        elif lines:
            first_lines.extend(lines)
            last_lines.extend(lines)

    # Count occurrences
    all_candidates = first_lines + last_lines
    counter = Counter(all_candidates)

    # Find patterns that appear frequently
    repeated = {text for text, count in counter.items() if count >= min_occurrences}

    # Filter out very short patterns (likely not headers/footers)
    repeated = {text for text in repeated if len(text) > 5}

    return repeated


def remove_page_numbers(text: str) -> str:
    """Remove common page number patterns.

    Args:
        text: Text content

    Returns:
        Text with page numbers removed
    """
    import re

    # Pattern: "Page 1", "第1页", "- 1 -", etc.
    patterns = [
        r"^Page\s+\d+\s*$",
        r"^第\s*\d+\s*页\s*$",
        r"^-\s*\d+\s*-\s*$",
        r"^\d+\s*/\s*\d+\s*$",
        r"^\[\s*\d+\s*\]\s*$",
    ]

    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        line_stripped = line.strip()
        is_page_number = any(re.match(pattern, line_stripped, re.IGNORECASE) for pattern in patterns)
        if not is_page_number:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def clean_page_content(content: str, repeated_patterns: set[str]) -> str:
    """Clean page content by removing headers, footers, and page numbers.

    Args:
        content: Page text content
        repeated_patterns: Set of repeated patterns to remove

    Returns:
        Cleaned content
    """
    # Remove page numbers
    content = remove_page_numbers(content)

    # Remove repeated patterns
    lines = content.split("\n")
    cleaned_lines = []

    for line in lines:
        line_stripped = line.strip()
        # Skip if line matches any repeated pattern
        if line_stripped not in repeated_patterns:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)


def clean_pdf_pages(pages_content: list[str]) -> list[str]:
    """Clean all pages by removing headers, footers, and noise.

    Args:
        pages_content: List of page text content

    Returns:
        List of cleaned page content
    """
    # Detect repeated patterns
    repeated_patterns = detect_repeated_patterns(pages_content)

    # Clean each page
    cleaned_pages = []
    for content in pages_content:
        cleaned = clean_page_content(content, repeated_patterns)
        # Only keep non-empty pages
        if cleaned.strip():
            cleaned_pages.append(cleaned)

    return cleaned_pages
