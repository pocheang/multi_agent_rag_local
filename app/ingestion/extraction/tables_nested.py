"""Nested table detection and flattening."""

import re


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


def extract_nested_tables(text: str) -> list[str]:
    """Extract nested tables as separate tables.

    Args:
        text: Markdown text

    Returns:
        List of table texts (parent + nested)
    """
    tables = []

    # Find main table
    lines = text.split("\n")
    table_lines = []
    nested_content = []

    for line in lines:
        if "|" in line:
            table_lines.append(line)

            # Check for nested content
            cells = [c.strip() for c in line.split("|") if c.strip()]
            for cell in cells:
                if "|" in cell:
                    # Extract nested table
                    nested_content.append(cell)

    if table_lines:
        tables.append("\n".join(table_lines))

    # Process nested content
    for nested in nested_content:
        if "|" in nested:
            tables.append(nested)

    return tables


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


def split_wide_table(text: str, max_columns: int = 6) -> list[str]:
    """Split very wide tables into multiple narrower tables.

    Args:
        text: Markdown table text
        max_columns: Maximum columns per table

    Returns:
        List of table texts
    """
    lines = text.split("\n")
    if not lines:
        return [text]

    # Find header line
    header_line = None

    for i, line in enumerate(lines):
        if "|" in line:
            header_line = line
            if i + 1 < len(lines) and re.match(r"^\|[\s\-:]+\|", lines[i + 1].strip()):
                lines[i + 1]
                break

    if not header_line:
        return [text]

    # Count columns
    header_cells = [c.strip() for c in header_line.split("|") if c.strip()]
    num_columns = len(header_cells)

    if num_columns <= max_columns:
        return [text]

    # Split into multiple tables
    tables = []
    for start_col in range(0, num_columns, max_columns):
        end_col = min(start_col + max_columns, num_columns)

        # Extract columns
        sub_table_lines = []
        for line in lines:
            if "|" not in line:
                sub_table_lines.append(line)
                continue

            cells = [c.strip() for c in line.split("|")]
            cells = [c for c in cells if c or cells.index(c) > 0]  # Keep structure

            # Extract subset of columns
            if len(cells) > start_col:
                sub_cells = cells[start_col:end_col]
                sub_line = "| " + " | ".join(sub_cells) + " |"
                sub_table_lines.append(sub_line)

        tables.append("\n".join(sub_table_lines))

    return tables
