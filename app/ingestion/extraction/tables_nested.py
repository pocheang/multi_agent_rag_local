"""Nested table detection and flattening."""


def detect_nested_table(text: str) -> bool:
    """Detect if text contains nested tables (table within table cells).

    Args:
        text: Markdown text

    Returns:
        True if nested tables detected
    """
    lines = [line.strip() for line in text.split("\n") if line.strip()]

    # Look for patterns like: | cell1 | cell2: | inner | table | |
    # or cells with multiple pipe separators
    for line in lines:
        if "|" not in line:
            continue

        # Split by pipes
        cells = [cell.strip() for cell in line.split("|")]
        cells = [c for c in cells if c]  # Remove empty

        # Check if any cell contains pipes (nested table indicator)
        for cell in cells:
            # Count pipes in cell content
            if cell.count("|") > 0:
                return True

    return False


def flatten_nested_table(text: str) -> str:
    """Flatten nested tables into single-level structure.

    Args:
        text: Markdown text with potential nested tables

    Returns:
        Flattened text
    """
    if not detect_nested_table(text):
        return text

    lines = text.split("\n")
    flattened_lines = []

    for line in lines:
        if "|" not in line:
            flattened_lines.append(line)
            continue

        # Process table row
        cells = line.split("|")
        processed_cells = []

        for cell in cells:
            cell = cell.strip()
            if not cell:
                processed_cells.append("")
                continue

            # If cell contains nested table markers, flatten it
            # Replace inner pipes with semicolons
            if "|" in cell:
                cell = cell.replace("|", "; ")

            processed_cells.append(cell)

        # Reconstruct line
        flattened_line = "| " + " | ".join(processed_cells) + " |"
        flattened_lines.append(flattened_line)

    return "\n".join(flattened_lines)


def simplify_complex_table(text: str) -> str:
    """Simplify complex tables for better LLM understanding.

    Args:
        text: Markdown table text

    Returns:
        Simplified table text
    """
    # Flatten nested tables
    text = flatten_nested_table(text)

    # Remove excessive whitespace
    lines = text.split("\n")
    cleaned_lines = []

    for line in lines:
        if "|" in line:
            # Normalize cell spacing
            cells = [c.strip() for c in line.split("|")]
            cleaned_line = "| " + " | ".join(cells) + " |"
            cleaned_lines.append(cleaned_line)
        else:
            cleaned_lines.append(line)

    return "\n".join(cleaned_lines)
