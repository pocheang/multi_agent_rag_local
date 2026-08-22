"""Enhanced document indexing with Chinese text processing."""

import logging
from typing import Any

from langchain_core.documents import Document

from app.services.language.chinese_query_preprocessor import ChineseQueryPreprocessor
from app.services.language.chinese_tokenizer import get_tokenizer

logger = logging.getLogger(__name__)


class ChineseDocumentIndexer:
    """Handles Chinese document preprocessing for indexing."""

    def __init__(self):
        """Initialize the indexer."""
        self.tokenizer = get_tokenizer()
        self.preprocessor = ChineseQueryPreprocessor(
            enable_synonym_expansion=False,  # Don't expand during indexing
            enable_stopword_removal=False,  # Keep all content for indexing
        )

    def preprocess_document(self, document: Document) -> Document:
        """Preprocess a document for Chinese text indexing.

        Args:
            document: Input document

        Returns:
            Preprocessed document with enhanced metadata
        """
        content = document.page_content
        metadata = document.metadata.copy()

        # Detect language
        language = self.preprocessor.detect_language(content)
        metadata["language"] = language

        # Normalize text
        normalized_content = self.preprocessor.normalize_text(content)

        # For Chinese content, add tokenized version to metadata
        if language in ["chinese", "mixed"]:
            # Tokenize for better indexing
            tokens = self.tokenizer.tokenize(normalized_content)
            metadata["tokens"] = tokens
            metadata["token_count"] = len(tokens)

            # Extract keywords for metadata
            keywords = self.tokenizer.extract_keywords(content, topK=10)
            metadata["keywords"] = keywords

            # Add segmented text as additional field for BM25
            metadata["segmented_text"] = " ".join(tokens)

        # Create new document with enhanced metadata
        enhanced_doc = Document(page_content=normalized_content, metadata=metadata)

        return enhanced_doc

    def preprocess_documents(self, documents: list[Document]) -> list[Document]:
        """Preprocess multiple documents.

        Args:
            documents: List of input documents

        Returns:
            List of preprocessed documents
        """
        processed = []
        for doc in documents:
            try:
                processed_doc = self.preprocess_document(doc)
                processed.append(processed_doc)
            except Exception as e:
                logger.error(f"Failed to preprocess document: {e}")
                # Keep original document if preprocessing fails
                processed.append(doc)

        logger.info(f"Preprocessed {len(processed)} documents for indexing")
        return processed

    def create_searchable_text(self, document: Document) -> str:
        """Create searchable text representation for a document.

        For Chinese documents, this includes both original and segmented text.

        Args:
            document: Input document

        Returns:
            Searchable text string
        """
        content = document.page_content
        metadata = document.metadata

        # Start with normalized content
        searchable = self.preprocessor.normalize_text(content)

        # For Chinese content, append segmented version
        if metadata.get("language") in ["chinese", "mixed"]:
            segmented = metadata.get("segmented_text", "")
            if segmented:
                searchable = f"{searchable}\n{segmented}"

        return searchable

    def extract_metadata_for_filtering(self, document: Document) -> dict[str, Any]:
        """Extract metadata useful for filtering and ranking.

        Args:
            document: Input document

        Returns:
            Dictionary of filterable metadata
        """
        metadata = document.metadata.copy()

        # Add computed fields
        content = document.page_content
        metadata["content_length"] = len(content)

        # Language detection
        if "language" not in metadata:
            metadata["language"] = self.preprocessor.detect_language(content)

        # For Chinese content, add keyword density
        if metadata["language"] in ["chinese", "mixed"]:
            keywords = self.tokenizer.extract_keywords(content, topK=5, withWeight=True)
            if keywords:
                # Average keyword weight as a quality signal
                avg_weight = sum(w for _, w in keywords) / len(keywords)
                metadata["keyword_density"] = avg_weight

        return metadata


class ChineseAwareChunker:
    """Chunks Chinese documents with awareness of sentence boundaries."""

    def __init__(self, chunk_size: int = 500, chunk_overlap: int = 50):
        """Initialize the chunker.

        Args:
            chunk_size: Target chunk size in characters
            chunk_overlap: Overlap between chunks in characters
        """
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.tokenizer = get_tokenizer()

    def split_text(self, text: str) -> list[str]:
        """Split text into chunks respecting Chinese sentence boundaries.

        Args:
            text: Input text

        Returns:
            List of text chunks
        """
        # Chinese sentence delimiters
        sentence_delimiters = ["。", "！", "？", "；", "\n"]

        # Split into sentences
        sentences = []
        current_sentence = ""

        for char in text:
            current_sentence += char
            if char in sentence_delimiters:
                if current_sentence.strip():
                    sentences.append(current_sentence.strip())
                current_sentence = ""

        # Add remaining text
        if current_sentence.strip():
            sentences.append(current_sentence.strip())

        # Combine sentences into chunks
        chunks = []
        current_chunk = ""

        for sentence in sentences:
            # If adding this sentence exceeds chunk size, save current chunk
            if len(current_chunk) + len(sentence) > self.chunk_size and current_chunk:
                chunks.append(current_chunk)

                # Start new chunk with overlap
                if self.chunk_overlap > 0:
                    # Take last N characters as overlap
                    overlap_text = current_chunk[-self.chunk_overlap :]
                    current_chunk = overlap_text + sentence
                else:
                    current_chunk = sentence
            else:
                current_chunk += sentence

        # Add final chunk
        if current_chunk:
            chunks.append(current_chunk)

        return chunks

    def chunk_document(self, document: Document) -> list[Document]:
        """Chunk a document into smaller pieces.

        Args:
            document: Input document

        Returns:
            List of chunked documents
        """
        text = document.page_content
        chunks = self.split_text(text)

        chunked_docs = []
        for i, chunk in enumerate(chunks):
            metadata = document.metadata.copy()
            metadata["chunk_index"] = i
            metadata["total_chunks"] = len(chunks)

            chunked_doc = Document(page_content=chunk, metadata=metadata)
            chunked_docs.append(chunked_doc)

        return chunked_docs


# Global instances
_indexer: ChineseDocumentIndexer | None = None
_chunker: ChineseAwareChunker | None = None


def get_indexer() -> ChineseDocumentIndexer:
    """Get or create the global indexer instance."""
    global _indexer
    if _indexer is None:
        _indexer = ChineseDocumentIndexer()
    return _indexer


def get_chunker(chunk_size: int = 500, chunk_overlap: int = 50) -> ChineseAwareChunker:
    """Get or create the global chunker instance."""
    global _chunker
    if _chunker is None:
        _chunker = ChineseAwareChunker(chunk_size, chunk_overlap)
    return _chunker
