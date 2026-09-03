"""Smart document chunking service for multi-modal RAG."""

import hashlib
import logging
import re
from dataclasses import dataclass
from pathlib import Path

from app.core.config import get_settings
from app.services.multimodal.models import (
    ChartContent,
    DocumentChunk,
    ImageContent,
    TableContent,
)

logger = logging.getLogger(__name__)


@dataclass
class Section:
    """Document section with heading and content."""

    heading: str | None
    level: int  # Heading level (1-6)
    text: str
    page_numbers: list[int]
    images: list[ImageContent]
    tables: list[TableContent]
    charts: list[ChartContent]
    start_position: tuple[int, float]  # (page, y_position)
    end_position: tuple[int, float]


class SmartChunker:
    """Intelligently chunk documents based on structure and content."""

    def __init__(self):
        self.settings = get_settings()
        self.max_chunk_size = 1000  # Max characters per chunk
        self.min_chunk_size = 200  # Min characters per chunk
        self.overlap_size = 100  # Overlap between chunks

        # Heading detection patterns
        self.heading_patterns = [
            r"^#{1,6}\s+(.+)$",  # Markdown headings
            r"^([A-Z][A-Za-z\s]+)$",  # All caps or title case on own line
            r"^(\d+\.)+\s+(.+)$",  # Numbered sections (1.1, 1.2.3)
            r"^(第[一二三四五六七八九十]+章|Chapter\s+\d+)",  # Chapter markers
        ]

    async def chunk_document(
        self,
        pdf_path: str | Path,
        doc_id: str,
        images: list[ImageContent] | None = None,
        tables: list[TableContent] | None = None,
        charts: list[ChartContent] | None = None,
    ) -> list[DocumentChunk]:
        """Chunk document intelligently based on structure.

        Args:
            pdf_path: Path to PDF file
            doc_id: Document identifier
            images: Pre-extracted images
            tables: Pre-extracted tables
            charts: Pre-extracted charts

        Returns:
            List of DocumentChunk objects
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        images = images or []
        tables = tables or []
        charts = charts or []

        try:
            # Extract document structure
            sections = await self._extract_sections(pdf_path, doc_id)

            # Associate multi-modal content with sections
            sections = self._associate_multimodal_content(sections, images, tables, charts)

            # Create chunks from sections
            chunks = self._create_chunks_from_sections(sections, doc_id)

            logger.info(f"Created {len(chunks)} chunks from {pdf_path.name} ({len(sections)} sections)")

            return chunks

        except Exception:
            logger.exception(f"Error chunking document {pdf_path}")
            raise

    async def _extract_sections(self, pdf_path: Path, doc_id: str) -> list[Section]:
        """Extract document sections based on structure.

        Args:
            pdf_path: Path to PDF
            doc_id: Document ID

        Returns:
            List of Section objects
        """
        sections: list[Section] = []
        current_section: Section | None = None

        try:
            import fitz  # PyMuPDF, from the optional `multimodal` extra

            with fitz.open(str(pdf_path)) as doc:
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    blocks = page.get_text("blocks")  # Get text blocks with positions

                    for block in blocks:
                        x0, y0, x1, y1, text, block_no, block_type = block

                        if block_type != 0:  # Only text blocks
                            continue

                        text = text.strip()
                        if not text:
                            continue

                        # Check if this is a heading
                        is_heading, heading_level = self._is_heading(text, y0, page.rect.height)

                        if is_heading:
                            # Save previous section
                            if current_section:
                                sections.append(current_section)

                            # Start new section
                            current_section = Section(
                                heading=text,
                                level=heading_level,
                                text="",
                                page_numbers=[page_num + 1],
                                images=[],
                                tables=[],
                                charts=[],
                                start_position=(page_num, y0),
                                end_position=(page_num, y1),
                            )
                        else:
                            # Add to current section
                            if current_section is None:
                                # Create default section if no heading yet
                                current_section = Section(
                                    heading=None,
                                    level=0,
                                    text="",
                                    page_numbers=[page_num + 1],
                                    images=[],
                                    tables=[],
                                    charts=[],
                                    start_position=(page_num, y0),
                                    end_position=(page_num, y1),
                                )

                            current_section.text += text + "\n"
                            current_section.end_position = (page_num, y1)

                            # Track page numbers
                            if page_num + 1 not in current_section.page_numbers:
                                current_section.page_numbers.append(page_num + 1)

                # Add last section
                if current_section:
                    sections.append(current_section)

            # If no sections detected, create one section per page
            if not sections:
                logger.warning(f"No sections detected in {pdf_path.name}, using page-based chunking")
                sections = await self._fallback_page_chunking(pdf_path, doc_id)

        except Exception:
            logger.exception("Error extracting sections")
            raise

        return sections

    def _is_heading(self, text: str, y_position: float, page_height: float) -> tuple[bool, int]:
        """Determine if text block is a heading.

        Args:
            text: Text content
            y_position: Y position on page
            page_height: Total page height

        Returns:
            Tuple of (is_heading, heading_level)
        """
        # Check text patterns
        for i, pattern in enumerate(self.heading_patterns):
            if re.match(pattern, text.strip()):
                # Estimate level based on pattern and position
                level = min(i + 1, 6)
                return True, level

        # Check text characteristics
        words = text.split()
        if len(words) <= 10:  # Short text
            # Check if mostly capitalized or title case
            if text.isupper() or text.istitle():
                # Position-based level (top = higher level)
                relative_pos = y_position / page_height
                if relative_pos < 0.1:
                    level = 1
                elif relative_pos < 0.2:
                    level = 2
                else:
                    level = 3
                return True, level

        return False, 0

    async def _fallback_page_chunking(self, pdf_path: Path, doc_id: str) -> list[Section]:
        """Fallback: create sections based on pages."""
        sections: list[Section] = []

        try:
            import fitz  # PyMuPDF, from the optional `multimodal` extra

            with fitz.open(str(pdf_path)) as doc:
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    text = page.get_text()

                    section = Section(
                        heading=f"Page {page_num + 1}",
                        level=1,
                        text=text,
                        page_numbers=[page_num + 1],
                        images=[],
                        tables=[],
                        charts=[],
                        start_position=(page_num, 0),
                        end_position=(page_num, page.rect.height),
                    )
                    sections.append(section)

        except Exception as e:
            logger.exception(f"Error in fallback chunking: {e}")
            raise

        return sections

    def _associate_multimodal_content(
        self,
        sections: list[Section],
        images: list[ImageContent],
        tables: list[TableContent],
        charts: list[ChartContent],
    ) -> list[Section]:
        """Associate images, tables, and charts with sections.

        Args:
            sections: List of sections
            images: List of images
            tables: List of tables
            charts: List of charts

        Returns:
            Sections with associated content
        """
        # Group content by page
        images_by_page: dict[int, list[ImageContent]] = {}
        tables_by_page: dict[int, list[TableContent]] = {}
        charts_by_page: dict[int, list[ChartContent]] = {}

        for img in images:
            images_by_page.setdefault(img.page_number, []).append(img)

        for tbl in tables:
            tables_by_page.setdefault(tbl.page_number, []).append(tbl)

        for chart in charts:
            charts_by_page.setdefault(chart.page_number, []).append(chart)

        # Associate with sections
        for section in sections:
            for page_num in section.page_numbers:
                # Add images from this page
                if page_num in images_by_page:
                    section.images.extend(images_by_page[page_num])

                # Add tables from this page
                if page_num in tables_by_page:
                    section.tables.extend(tables_by_page[page_num])

                # Add charts from this page
                if page_num in charts_by_page:
                    section.charts.extend(charts_by_page[page_num])

        return sections

    def _create_chunks_from_sections(self, sections: list[Section], doc_id: str) -> list[DocumentChunk]:
        """Create document chunks from sections.

        Args:
            sections: List of sections
            doc_id: Document ID

        Returns:
            List of DocumentChunk objects
        """
        chunks: list[DocumentChunk] = []

        for section in sections:
            # If section is small enough, create single chunk
            if len(section.text) <= self.max_chunk_size:
                chunk = self._create_chunk_from_section(section, doc_id, 0)
                chunks.append(chunk)
            else:
                # Split large section into multiple chunks
                sub_chunks = self._split_section(section, doc_id)
                chunks.extend(sub_chunks)

        return chunks

    def _create_chunk_from_section(self, section: Section, doc_id: str, chunk_index: int) -> DocumentChunk:
        """Create a DocumentChunk from a Section.

        Args:
            section: Section object
            doc_id: Document ID
            chunk_index: Index for multi-chunk sections

        Returns:
            DocumentChunk object
        """
        # Generate chunk ID
        chunk_id = self._generate_chunk_id(doc_id, section.page_numbers[0], chunk_index)

        # Build metadata
        metadata = {
            "heading_level": section.level,
            "has_images": len(section.images) > 0,
            "has_tables": len(section.tables) > 0,
            "has_charts": len(section.charts) > 0,
            "num_images": len(section.images),
            "num_tables": len(section.tables),
            "num_charts": len(section.charts),
        }

        chunk = DocumentChunk(
            chunk_id=chunk_id,
            doc_id=doc_id,
            heading=section.heading,
            text_content=section.text,
            page_numbers=section.page_numbers,
            images=section.images,
            tables=section.tables,
            charts=section.charts,
            metadata=metadata,
        )

        return chunk

    def _split_section(self, section: Section, doc_id: str) -> list[DocumentChunk]:
        """Split large section into multiple chunks.

        Args:
            section: Section to split
            doc_id: Document ID

        Returns:
            List of DocumentChunk objects
        """
        chunks: list[DocumentChunk] = []
        text = section.text

        # Split by paragraphs first
        paragraphs = text.split("\n\n")

        current_text = ""
        current_paragraphs: list[str] = []
        chunk_index = 0

        for para in paragraphs:
            # Check if adding this paragraph exceeds max size
            if len(current_text) + len(para) > self.max_chunk_size and current_text:
                # Create chunk with current paragraphs
                chunk = self._create_text_chunk(section, doc_id, chunk_index, current_text, current_paragraphs)
                chunks.append(chunk)

                # Start new chunk with overlap
                current_text = current_text[-self.overlap_size :] if current_text else ""
                current_paragraphs = []
                chunk_index += 1

            current_text += para + "\n\n"
            current_paragraphs.append(para)

        # Add remaining text
        if current_text.strip():
            chunk = self._create_text_chunk(section, doc_id, chunk_index, current_text, current_paragraphs)
            chunks.append(chunk)

        # Distribute images/tables/charts across chunks
        # For simplicity, add all to first chunk
        if chunks:
            chunks[0].images = section.images
            chunks[0].tables = section.tables
            chunks[0].charts = section.charts

        return chunks

    def _create_text_chunk(
        self,
        section: Section,
        doc_id: str,
        chunk_index: int,
        text: str,
        paragraphs: list[str],
    ) -> DocumentChunk:
        """Create chunk from text."""
        chunk_id = self._generate_chunk_id(doc_id, section.page_numbers[0], chunk_index)

        metadata = {
            "heading_level": section.level,
            "chunk_index": chunk_index,
            "is_partial": True,  # Part of larger section
        }

        chunk = DocumentChunk(
            chunk_id=chunk_id,
            doc_id=doc_id,
            heading=section.heading,
            text_content=text.strip(),
            page_numbers=section.page_numbers,
            images=[],
            tables=[],
            charts=[],
            metadata=metadata,
        )

        return chunk

    def _generate_chunk_id(self, doc_id: str, page_num: int, chunk_index: int) -> str:
        """Generate unique chunk ID."""
        content = f"{doc_id}:page{page_num}:chunk{chunk_index}"
        return f"chk_{hashlib.md5(content.encode()).hexdigest()[:12]}"

    def format_chunk_for_indexing(self, chunk: DocumentChunk) -> str:
        """Format chunk as text for vector indexing.

        Args:
            chunk: DocumentChunk object

        Returns:
            Formatted text
        """
        parts = []

        # Add heading
        if chunk.heading:
            parts.append(f"# {chunk.heading}\n")

        # Add text content
        parts.append(chunk.text_content)

        # Add table summaries
        for table in chunk.tables:
            parts.append(f"\n[Table: {table.summary}]")

        # Add image descriptions
        for image in chunk.images:
            parts.append(f"\n[Image: {image.description}]")

        # Add chart descriptions
        for chart in chunk.charts:
            if chart.title:
                parts.append(f"\n[Chart: {chart.title} - {chart.description}]")
            else:
                parts.append(f"\n[Chart: {chart.description}]")

        return "\n".join(parts)
