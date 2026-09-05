"""Table indexing for multi-modal RAG."""

from __future__ import annotations

import logging

from app.services.multimodal.models import TableContent

logger = logging.getLogger(__name__)


class TableExtractor:
    """Index a table that ingestion has already parsed.

    The pdfplumber and PyMuPDF extractors that used to live here had no callers:
    `_index_tables` reads the loader's rendered markdown through
    `_table_from_markdown`, which is what keeps a table's header attached to it.
    The pandas dependency went with them.
    """

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
