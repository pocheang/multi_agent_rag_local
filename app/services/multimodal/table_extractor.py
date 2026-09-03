"""Table extraction service for multi-modal RAG."""

import hashlib
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from app.core.config import get_settings
from app.services.multimodal.models import TableContent

logger = logging.getLogger(__name__)


class TableExtractor:
    """Extract and parse tables from documents."""

    def __init__(self):
        self.settings = get_settings()
        self.enable_table_extraction = getattr(self.settings, "enable_table_extraction", True)
        self.min_table_rows = 2  # Minimum rows to consider as table
        self.min_table_cols = 2  # Minimum columns to consider as table

    async def extract_tables_from_pdf(self, pdf_path: str | Path, doc_id: str) -> list[TableContent]:
        """Extract tables from PDF document.

        Args:
            pdf_path: Path to PDF file
            doc_id: Document identifier

        Returns:
            List of TableContent objects
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        tables: list[TableContent] = []

        try:
            # Try pdfplumber first (better for most PDFs)
            tables = await self._extract_with_pdfplumber(pdf_path, doc_id)

            # If pdfplumber fails or finds no tables, try PyMuPDF
            if not tables:
                logger.info("Trying PyMuPDF table extraction as fallback")
                tables = await self._extract_with_pymupdf(pdf_path, doc_id)

            logger.info(f"Extracted {len(tables)} tables from {pdf_path.name}")

        except Exception:
            logger.exception(f"Error extracting tables from {pdf_path}")
            raise

        return tables

    async def _extract_with_pdfplumber(self, pdf_path: Path, doc_id: str) -> list[TableContent]:
        """Extract tables using pdfplumber."""
        tables: list[TableContent] = []

        try:
            import pdfplumber

            with pdfplumber.open(str(pdf_path)) as pdf:
                for page_num, page in enumerate(pdf.pages, start=1):
                    page_tables = page.extract_tables()

                    for table_index, table_data in enumerate(page_tables):
                        if not table_data or len(table_data) < self.min_table_rows:
                            continue

                        try:
                            # Convert to DataFrame
                            df = pd.DataFrame(table_data[1:], columns=table_data[0])

                            # Filter empty columns
                            df = df.dropna(axis=1, how="all")

                            # Filter if too few columns
                            if len(df.columns) < self.min_table_cols:
                                continue

                            # Generate table ID
                            table_id = self._generate_table_id(doc_id, page_num, table_index)

                            # Generate summary
                            summary = self._generate_table_summary(df)

                            # Get bounding box if available
                            bbox = self._get_table_bbox_pdfplumber(page, table_index)

                            table_content = TableContent(
                                table_id=table_id,
                                doc_id=doc_id,
                                page_number=page_num,
                                headers=df.columns.tolist(),
                                rows=df.values.tolist(),
                                summary=summary,
                                bbox=bbox,
                                metadata={
                                    "num_rows": len(df),
                                    "num_cols": len(df.columns),
                                    "extraction_method": "pdfplumber",
                                },
                            )

                            tables.append(table_content)

                        except Exception:
                            logger.exception(f"Error processing table {table_index} on page {page_num}")
                            continue

        except ImportError:
            logger.exception("pdfplumber not installed. Install with: pip install pdfplumber")
            raise
        except Exception:
            logger.exception("pdfplumber extraction error")
            raise

        return tables

    async def _extract_with_pymupdf(self, pdf_path: Path, doc_id: str) -> list[TableContent]:
        """Extract tables using PyMuPDF (fallback method)."""
        tables: list[TableContent] = []

        try:
            import fitz  # PyMuPDF, from the optional `multimodal` extra

            with fitz.open(str(pdf_path)) as doc:
                for page_num in range(len(doc)):
                    page = doc[page_num]

                    # Find tables using PyMuPDF's table finder
                    page_tables = page.find_tables()

                    for table_index, table in enumerate(page_tables):
                        try:
                            # Extract table data
                            table_data = table.extract()

                            if not table_data or len(table_data) < self.min_table_rows:
                                continue

                            # Convert to DataFrame
                            df = pd.DataFrame(table_data[1:], columns=table_data[0])

                            # Filter empty columns
                            df = df.dropna(axis=1, how="all")

                            if len(df.columns) < self.min_table_cols:
                                continue

                            # Generate table ID
                            table_id = self._generate_table_id(doc_id, page_num + 1, table_index)

                            # Generate summary
                            summary = self._generate_table_summary(df)

                            # Get bounding box
                            bbox = table.bbox  # PyMuPDF provides bbox directly

                            table_content = TableContent(
                                table_id=table_id,
                                doc_id=doc_id,
                                page_number=page_num + 1,
                                headers=df.columns.tolist(),
                                rows=df.values.tolist(),
                                summary=summary,
                                bbox=bbox,
                                metadata={
                                    "num_rows": len(df),
                                    "num_cols": len(df.columns),
                                    "extraction_method": "pymupdf",
                                },
                            )

                            tables.append(table_content)

                        except Exception:
                            logger.exception(f"Error processing table {table_index} on page {page_num + 1}")
                            continue

        except Exception as e:
            logger.exception(f"PyMuPDF extraction error: {e}")
            raise

        return tables

    def _get_table_bbox_pdfplumber(self, page: Any, table_index: int) -> tuple[float, float, float, float] | None:
        """Get bounding box for table using pdfplumber."""
        try:
            # pdfplumber tables have bbox attribute
            tables = page.find_tables()
            if tables and table_index < len(tables):
                bbox = tables[table_index].bbox
                return (bbox[0], bbox[1], bbox[2] - bbox[0], bbox[3] - bbox[1])
        except Exception as e:
            logger.debug(f"Could not get table bbox: {e}")
        return None

    def _generate_table_id(self, doc_id: str, page_num: int, table_index: int) -> str:
        """Generate unique table ID."""
        content = f"{doc_id}:page{page_num}:table{table_index}"
        return f"tbl_{hashlib.md5(content.encode()).hexdigest()[:12]}"

    def _generate_table_summary(self, df: pd.DataFrame) -> str:
        """Generate human-readable table summary.

        Args:
            df: DataFrame containing table data

        Returns:
            Summary text
        """
        try:
            summary_parts = []

            # Basic info
            num_rows, num_cols = df.shape
            summary_parts.append(f"Table with {num_rows} rows and {num_cols} columns.")

            # Column headers
            headers = ", ".join([str(h) for h in df.columns[:5]])
            if len(df.columns) > 5:
                headers += f", ... ({len(df.columns) - 5} more)"
            summary_parts.append(f"Columns: {headers}.")

            # Sample first row
            if not df.empty:
                first_row = df.iloc[0].tolist()
                first_row_str = ", ".join([str(v)[:50] for v in first_row[:3]])
                if len(first_row) > 3:
                    first_row_str += ", ..."
                summary_parts.append(f"Sample data: {first_row_str}.")

            # Numeric column statistics
            numeric_cols = df.select_dtypes(include=["number"]).columns
            if len(numeric_cols) > 0:
                stats_parts = []
                for col in numeric_cols[:3]:  # First 3 numeric columns
                    try:
                        mean_val = df[col].mean()
                        if pd.notna(mean_val):
                            stats_parts.append(f"{col} (avg: {mean_val:.2f})")
                    except Exception:
                        pass
                if stats_parts:
                    summary_parts.append(f"Numeric columns: {', '.join(stats_parts)}.")

            return " ".join(summary_parts)

        except Exception:
            logger.exception("Error generating table summary")
            return f"Table with {len(df)} rows and {len(df.columns)} columns."

    def parse_table_to_dataframe(self, table: TableContent) -> pd.DataFrame:
        """Convert TableContent back to pandas DataFrame.

        Args:
            table: TableContent object

        Returns:
            pandas DataFrame
        """
        return pd.DataFrame(table.rows, columns=table.headers)

    def format_table_as_markdown(self, table: TableContent) -> str:
        """Format table as markdown for display.

        Args:
            table: TableContent object

        Returns:
            Markdown formatted table
        """
        try:
            df = self.parse_table_to_dataframe(table)
            return df.to_markdown(index=False)
        except Exception:
            logger.exception("Error formatting table as markdown")
            return f"[Table {table.table_id} on page {table.page_number}]"

    def format_table_as_text(self, table: TableContent, max_rows: int = 10) -> str:
        """Format table as plain text for indexing.

        Args:
            table: TableContent object
            max_rows: Maximum rows to include

        Returns:
            Text representation
        """
        try:
            lines = []

            # Add headers
            lines.append("Table: " + " | ".join(table.headers))
            lines.append("-" * 50)

            # Add rows (limited)
            for _i, row in enumerate(table.rows[:max_rows]):
                row_str = " | ".join([str(cell) for cell in row])
                lines.append(row_str)

            # Add truncation notice
            if len(table.rows) > max_rows:
                lines.append(f"... ({len(table.rows) - max_rows} more rows)")

            return "\n".join(lines)

        except Exception:
            logger.exception("Error formatting table as text")
            return f"[Table {table.table_id}]"

    def index_table(self, table: TableContent, collection_name: str = "table_summaries") -> None:
        """Index table content in vector database.

        Synchronous: it awaits nothing, and its caller is document ingestion,
        which runs in a worker thread where an event loop must not be driven.

        Args:
            table: TableContent object
            collection_name: ChromaDB collection name
        """
        try:
            from app.retrievers.stores.vector import get_named_vector_store

            store = get_named_vector_store(collection_name)

            # Create text representation for indexing
            text_to_index = f"{table.summary}\n\n{self.format_table_as_text(table)}"

            # Add to collection
            store.add_texts(
                ids=[table.table_id],
                texts=[text_to_index],
                metadatas=[
                    {
                        "doc_id": table.doc_id,
                        "document_id": table.metadata.get("document_id", table.doc_id),
                        "tenant_id": table.metadata.get("tenant_id", "shared"),
                        # Absent keys do not match `$eq`, so a table indexed
                        # without these is invisible rather than public.
                        "owner_user_id": table.metadata.get("owner_user_id", ""),
                        "visibility": table.metadata.get("visibility", "private"),
                        "version": table.metadata.get("version", 1),
                        "page_number": table.page_number,
                        "source": table.metadata.get("source", table.doc_id),
                        "type": "table",
                        "num_rows": table.metadata.get("num_rows", 0),
                        "num_cols": table.metadata.get("num_cols", 0),
                        "extraction_method": table.metadata.get("extraction_method", "unknown"),
                    }
                ],
            )

            logger.info(f"Indexed table {table.table_id} in collection {collection_name}")

        except Exception:
            logger.exception(f"Error indexing table {table.table_id}")
            raise

    async def extract_tables_batch(
        self, pdf_paths: list[str | Path], doc_ids: list[str]
    ) -> dict[str, list[TableContent]]:
        """Extract tables from multiple PDFs.

        Args:
            pdf_paths: List of PDF paths
            doc_ids: Corresponding document IDs

        Returns:
            Dictionary mapping doc_id to list of tables
        """
        if len(pdf_paths) != len(doc_ids):
            raise ValueError("pdf_paths and doc_ids must have same length")

        results: dict[str, list[TableContent]] = {}

        for pdf_path, doc_id in zip(pdf_paths, doc_ids, strict=False):
            try:
                tables = await self.extract_tables_from_pdf(pdf_path, doc_id)
                results[doc_id] = tables
            except Exception:
                logger.exception(f"Error extracting tables from {pdf_path}")
                results[doc_id] = []

        return results
