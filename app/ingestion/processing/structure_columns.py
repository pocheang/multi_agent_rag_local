import logging

logger = logging.getLogger(__name__)

"""Multi-column layout detection and text reordering."""


def detect_column_layout(text_blocks: list[dict]) -> int:
    """Detect number of columns in a page layout.

    Args:
        text_blocks: List of text blocks with position info
                     Each block: {"text": str, "x": float, "y": float, "width": float}

    Returns:
        Number of columns detected (1, 2, or 3)
    """
    if not text_blocks or len(text_blocks) < 3:
        return 1

    # Get x-coordinates of all blocks
    x_coords = [block["x"] for block in text_blocks]

    # Cluster x-coordinates to find column boundaries
    x_coords_sorted = sorted(set(x_coords))

    # If most blocks start at similar x positions, likely multi-column
    # Simple heuristic: check for 2-3 distinct x-position clusters
    if len(x_coords_sorted) < 2:
        return 1

    # Calculate gaps between x positions
    gaps = []
    for i in range(len(x_coords_sorted) - 1):
        gap = x_coords_sorted[i + 1] - x_coords_sorted[i]
        gaps.append(gap)

    # If there's a significant gap, likely column boundary
    if gaps:
        avg_gap = sum(gaps) / len(gaps)
        large_gaps = [g for g in gaps if g > avg_gap * 2]

        if len(large_gaps) >= 1:
            return len(large_gaps) + 1

    return 1


def reorder_multicolumn_text(text_blocks: list[dict], num_columns: int = 2) -> list[dict]:
    """Reorder text blocks for multi-column layout (left-to-right, top-to-bottom).

    Args:
        text_blocks: List of text blocks with position info
        num_columns: Number of columns

    Returns:
        Reordered text blocks
    """
    if num_columns == 1 or not text_blocks:
        # Single column: just sort by y position
        return sorted(text_blocks, key=lambda b: b["y"])

    # Multi-column: group by y position first, then sort by x within each row
    # Group blocks into rows (blocks with similar y positions)
    rows = []
    current_row = []
    y_threshold = 10  # pixels tolerance for same row

    sorted_by_y = sorted(text_blocks, key=lambda b: b["y"])

    for block in sorted_by_y:
        if not current_row:
            current_row.append(block)
        else:
            # Check if block is in same row as previous
            if abs(block["y"] - current_row[0]["y"]) <= y_threshold:
                current_row.append(block)
            else:
                # New row
                rows.append(current_row)
                current_row = [block]

    if current_row:
        rows.append(current_row)

    # Sort each row by x position (left to right)
    reordered = []
    for row in rows:
        sorted_row = sorted(row, key=lambda b: b["x"])
        reordered.extend(sorted_row)

    return reordered


def extract_text_blocks_from_page(page) -> list[dict]:
    """Extract text blocks with position info from a PDF page.

    Args:
        page: pypdf page object

    Returns:
        List of text blocks with position info
    """
    try:
        # Try to extract text with layout info
        # This is a simplified version - real implementation would use pdfplumber
        text = page.extract_text()
        if not text:
            return []

        # Fallback: treat as single block
        return [{"text": text, "x": 0, "y": 0, "width": 100}]

    except (ValueError, TypeError, AttributeError) as e:
        logger.debug(f"Failed to detect columns in text block: {e}")
        return []
    except Exception as e:
        logger.error(f"Unexpected error in column detection: {e}")
        return []


def reorder_page_text_multicolumn(page_text: str, has_multicolumn: bool = False) -> str:
    """Reorder page text if multi-column layout detected.

    Args:
        page_text: Raw page text
        has_multicolumn: Whether page has multi-column layout

    Returns:
        Reordered text
    """
    if not has_multicolumn:
        return page_text

    # Simple heuristic: if text has very short lines followed by more short lines,
    # might be multi-column (this is a fallback when we don't have position info)
    lines = page_text.split("\n")
    if len(lines) < 10:
        return page_text

    # Check average line length
    line_lengths = [len(line.strip()) for line in lines if line.strip()]
    if not line_lengths:
        return page_text

    avg_length = sum(line_lengths) / len(line_lengths)

    # If average line is very short (< 40 chars), might be multi-column
    if avg_length < 40:
        # Try to detect column break (empty lines or consistent indentation)
        # This is a simple heuristic - real implementation would need position data
        pass

    return page_text
