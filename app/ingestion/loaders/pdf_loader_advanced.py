"""Advanced PDF loader with all enhancements integrated."""

import logging
from pathlib import Path

from langchain_core.documents import Document

from app.ingestion.loaders.pdf_loader_enhanced import load_pdf_enhanced
from app.ingestion.processing.coreference import simple_coreference_resolution
from app.ingestion.processing.structure import add_section_metadata, extract_document_structure
from app.ingestion.extraction.formulas import enrich_text_with_formulas

logger = logging.getLogger(__name__)


def load_pdf_advanced(
    path: Path,
    by_page: bool = True,
    enable_structure: bool = True,
    enable_coreference: bool = True,
    enable_formula_enrichment: bool = True,
    enable_cleaning: bool = True,
    enable_table_merging: bool = True,
) -> list[Document]:
    """
    Load PDF with all advanced processing features.

    Features:
    - Document structure analysis (chapters, sections)
    - Coreference resolution (pronoun resolution)
    - Formula semantic extraction
    - All previous enhancements (cleaning, table merging, etc.)

    Args:
        path: Path to PDF file
        by_page: Return one Document per page
        enable_structure: Enable document structure analysis
        enable_coreference: Enable coreference resolution
        enable_formula_enrichment: Enable formula semantic extraction
        enable_cleaning: Enable header/footer removal
        enable_table_merging: Enable cross-page table merging

    Returns:
        List of Document objects with advanced processing
    """
    # Load with enhanced processing (cleaning, tables, etc.)
    docs = load_pdf_enhanced(
        path,
        by_page=by_page,
        enable_cleaning=enable_cleaning,
        enable_table_merging=enable_table_merging,
        enable_nested_table_handling=True,
    )

    if not docs:
        logger.warning(f"No documents loaded from {path.name}")
        return docs

    # Process each document
    processed_docs = []

    for doc in docs:
        content = doc.page_content
        metadata = doc.metadata.copy()

        try:
            # Step 1: Formula enrichment (optional)
            if enable_formula_enrichment:
                content = enrich_text_with_formulas(content)
                metadata["formula_enrichment"] = True

            # Step 2: Coreference resolution (optional)
            if enable_coreference:
                content = simple_coreference_resolution(content)
                metadata["coreference_resolved"] = True

            # Step 3: Document structure (optional)
            if enable_structure:
                sections = extract_document_structure(content, page=metadata.get("page"))
                if sections:
                    content = add_section_metadata(content, sections)
                    metadata["sections_count"] = len(sections)
                    metadata["has_structure"] = True

            # Create processed document
            processed_doc = Document(page_content=content, metadata=metadata)
            processed_docs.append(processed_doc)

        except Exception as e:
            logger.error(f"Advanced processing failed for page {metadata.get('page', '?')}: {e}", exc_info=True)
            # Keep original document on error
            processed_docs.append(doc)

    return processed_docs
