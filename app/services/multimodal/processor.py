"""Integrated multi-modal document processor."""

import asyncio
import logging
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.domain.knowledge import AccessScope
from app.services.multimodal.chart_analyzer import ChartAnalyzer
from app.services.multimodal.image_processor import ImageProcessor
from app.services.multimodal.models import ChartContent, DocumentChunk, ImageContent, TableContent
from app.services.multimodal.smart_chunker import SmartChunker
from app.services.multimodal.table_extractor import TableExtractor

logger = logging.getLogger(__name__)


class MultiModalDocumentProcessor:
    """Orchestrate multi-modal document processing pipeline."""

    def __init__(self):
        self.settings = get_settings()
        self.image_processor = ImageProcessor()
        self.table_extractor = TableExtractor()
        self.chart_analyzer = ChartAnalyzer()
        self.smart_chunker = SmartChunker()

        self.enable_image_processing = getattr(self.settings, "enable_image_processing", True)
        self.enable_table_extraction = getattr(self.settings, "enable_table_extraction", True)

    async def process_document(
        self,
        pdf_path: str | Path,
        doc_id: str,
        index_content: bool = True,
        *,
        tenant_id: str = "shared",
        version: int = 1,
    ) -> dict[str, Any]:
        """Process document with full multi-modal pipeline.

        Args:
            pdf_path: Path to PDF file
            doc_id: Document identifier
            index_content: Whether to index extracted content

        Returns:
            Dictionary with processing results
        """
        pdf_path = Path(pdf_path)
        logger.info(f"Starting multi-modal processing for {pdf_path.name}")

        results = {
            "doc_id": doc_id,
            "pdf_path": str(pdf_path),
            "images": [],
            "tables": [],
            "charts": [],
            "chunks": [],
            "stats": {},
        }

        try:
            # Phase 1: Extract images and tables in parallel
            logger.info("Phase 1: Extracting images and tables")
            extraction_tasks = []

            if self.enable_image_processing:
                extraction_tasks.append(
                    self.image_processor.extract_images_from_pdf(
                        pdf_path,
                        doc_id,
                        tenant_id=tenant_id,
                        version=version,
                    )
                )
            else:
                extraction_tasks.append(asyncio.sleep(0))  # Placeholder

            if self.enable_table_extraction:
                extraction_tasks.append(self.table_extractor.extract_tables_from_pdf(pdf_path, doc_id))
            else:
                extraction_tasks.append(asyncio.sleep(0))  # Placeholder

            extraction_results = await asyncio.gather(*extraction_tasks)

            images: list[ImageContent] = []
            tables: list[TableContent] = []

            if self.enable_image_processing:
                images = extraction_results[0] if isinstance(extraction_results[0], list) else []

            if self.enable_table_extraction:
                tables = extraction_results[1] if isinstance(extraction_results[1], list) else []
                for table in tables:
                    table.metadata.update(
                        {
                            "document_id": doc_id,
                            "tenant_id": tenant_id,
                            "version": version,
                            "source": str(pdf_path),
                        }
                    )

            logger.info(f"Extracted {len(images)} images and {len(tables)} tables")

            # Phase 2: Process images (descriptions + OCR) and analyze charts
            logger.info("Phase 2: Processing images and analyzing charts")
            charts: list[ChartContent] = []

            if images:
                # Process images concurrently
                images = await self.image_processor.process_images_batch(
                    images,
                    generate_descriptions=True,
                    perform_ocr=True,
                    use_claude_for_simple=True,
                    max_concurrent=5,
                )

                # Analyze which images are charts
                charts = await self.chart_analyzer.analyze_charts_batch(images, max_concurrent=3)

                logger.info(f"Identified {len(charts)} charts from {len(images)} images")

            # Phase 3: Smart chunking with multi-modal content
            logger.info("Phase 3: Creating intelligent document chunks")
            chunks = await self.smart_chunker.chunk_document(
                pdf_path, doc_id, images=images, tables=tables, charts=charts
            )
            for chunk in chunks:
                chunk.metadata.update(
                    {
                        "document_id": doc_id,
                        "tenant_id": tenant_id,
                        "version": version,
                        "source": str(pdf_path),
                    }
                )

            logger.info(f"Created {len(chunks)} document chunks")

            # Phase 4: Index content if requested
            if index_content:
                logger.info("Phase 4: Indexing multi-modal content")
                await self._index_all_content(images, tables, charts, chunks)

            # Compile results
            results["images"] = images
            results["tables"] = tables
            results["charts"] = charts
            results["chunks"] = chunks
            results["stats"] = {
                "num_images": len(images),
                "num_tables": len(tables),
                "num_charts": len(charts),
                "num_chunks": len(chunks),
                "chunks_with_images": sum(1 for c in chunks if c.images),
                "chunks_with_tables": sum(1 for c in chunks if c.tables),
                "chunks_with_charts": sum(1 for c in chunks if c.charts),
                "multimodal_chunks": sum(1 for c in chunks if c.has_multimodal_content),
            }

            logger.info(
                f"Multi-modal processing complete: {results['stats']['num_images']} images, "
                f"{results['stats']['num_tables']} tables, {results['stats']['num_charts']} charts, "
                f"{results['stats']['num_chunks']} chunks"
            )

            return results

        except Exception as e:
            logger.error(f"Error processing document {pdf_path}: {e}")
            raise

    async def _index_all_content(
        self,
        images: list[ImageContent],
        tables: list[TableContent],
        charts: list[ChartContent],
        chunks: list[DocumentChunk],
    ) -> None:
        """Index all extracted content in vector database.

        Args:
            images: Extracted images
            tables: Extracted tables
            charts: Analyzed charts
            chunks: Document chunks
        """
        indexing_tasks = []

        # Index images
        for image in images:
            if image.description and image.metadata.get("masking_status") in {"clean", "masked"}:
                indexing_tasks.append(self.image_processor.index_image(image))

        # Index tables
        for table in tables:
            indexing_tasks.append(self.table_extractor.index_table(table))

        # Index charts
        for chart in charts:
            indexing_tasks.append(self.chart_analyzer.index_chart(chart))

        # Index chunks
        for chunk in chunks:
            indexing_tasks.append(self._index_chunk(chunk))

        # Execute all indexing operations
        await asyncio.gather(*indexing_tasks, return_exceptions=True)

        logger.info(f"Indexed {len(images)} images, {len(tables)} tables, {len(charts)} charts, {len(chunks)} chunks")

    async def _index_chunk(self, chunk: DocumentChunk) -> None:
        """Index a document chunk in the main text collection.

        Args:
            chunk: DocumentChunk to index
        """
        try:
            from app.retrievers.stores.vector import get_named_vector_store

            store = get_named_vector_store("text_chunks")

            # Format chunk for indexing
            text = self.smart_chunker.format_chunk_for_indexing(chunk)

            # Add to collection
            store.add_texts(
                texts=[text],
                ids=[chunk.chunk_id],
                metadatas=[
                    {
                        "doc_id": chunk.doc_id,
                        "document_id": chunk.metadata.get("document_id", chunk.doc_id),
                        "tenant_id": chunk.metadata.get("tenant_id", "shared"),
                        "version": chunk.metadata.get("version", 1),
                        "source": chunk.metadata.get("source", chunk.doc_id),
                        "chunk_id": chunk.chunk_id,
                        "page_number": min(chunk.page_numbers) if chunk.page_numbers else 0,
                        "page_numbers": ",".join(map(str, chunk.page_numbers)),
                        "heading": chunk.heading or "",
                        "has_multimodal": chunk.has_multimodal_content,
                        "modalities": ",".join(chunk.modality_types),
                        **chunk.metadata,
                    }
                ],
            )

        except Exception as e:
            logger.error(f"Error indexing chunk {chunk.chunk_id}: {e}")

    async def reprocess_document_images(
        self,
        doc_id: str,
        pdf_path: str | Path,
        *,
        tenant_id: str = "shared",
        version: int = 1,
    ) -> dict[str, Any]:
        """Reprocess only images for an existing document.

        Useful for improving descriptions or adding OCR to existing indexed documents.

        Args:
            doc_id: Document identifier
            pdf_path: Path to PDF file

        Returns:
            Processing results
        """
        logger.info(f"Reprocessing images for document {doc_id}")

        # Extract images
        images = await self.image_processor.extract_images_from_pdf(
            pdf_path,
            doc_id,
            tenant_id=tenant_id,
            version=version,
        )

        # Process images
        images = await self.image_processor.process_images_batch(
            images,
            generate_descriptions=True,
            perform_ocr=True,
            use_claude_for_simple=True,
        )

        # Analyze charts
        charts = await self.chart_analyzer.analyze_charts_batch(images)

        # Re-index
        for image in images:
            if image.description and image.metadata.get("masking_status") in {"clean", "masked"}:
                await self.image_processor.index_image(image)

        for chart in charts:
            await self.chart_analyzer.index_chart(chart)

        return {
            "doc_id": doc_id,
            "num_images_processed": len(images),
            "num_charts_identified": len(charts),
        }

    async def get_document_statistics(self, doc_id: str, scope: AccessScope) -> dict[str, Any]:
        """Get statistics about multi-modal content for a document.

        Args:
            doc_id: Document identifier

        Returns:
            Statistics dictionary
        """
        from app.retrievers.multimodal_retriever import MultiModalRetriever

        retriever = MultiModalRetriever()

        # Retrieve all content for document
        results = await retriever.retrieve_by_doc_id(
            doc_id,
            scope,
            modalities=["text", "image", "table", "chart"],
        )

        stats = {
            "doc_id": doc_id,
            "num_text_chunks": len(results.get("text", [])),
            "num_images": len(results.get("image", [])),
            "num_tables": len(results.get("table", [])),
            "num_charts": len(results.get("chart", [])),
            "total_multimodal_items": (
                len(results.get("image", [])) + len(results.get("table", [])) + len(results.get("chart", []))
            ),
        }

        return stats
