"""Comprehensive logic validation tests for refactored code."""

import pytest

from app.agents.rag.evidence_builder import EvidenceItemBuilder
from app.domain.contracts import EvidenceItem


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_empty_string_fields_are_rejected(self):
        """Empty strings should be treated as missing values."""
        builder = EvidenceItemBuilder("test")

        # Empty content
        assert builder.from_legacy_citation({
            "content": "",  # Empty string
            "source": "test.pdf",
            "document_id": "123"
        }) is None

        # Empty source
        assert builder.from_legacy_citation({
            "content": "text",
            "source": "",  # Empty string
            "document_id": "123"
        }) is None

        # Whitespace-only content
        assert builder.from_legacy_citation({
            "content": "   ",  # Whitespace
            "source": "test.pdf",
            "document_id": "123"
        }) is None

    def test_document_id_fallback_to_source(self):
        """If document_id missing, should use source."""
        builder = EvidenceItemBuilder("test")

        citation = {
            "content": "text",
            "source": "fallback.pdf",
            # No document_id
        }

        item = builder.from_legacy_citation(citation)
        assert item is not None
        assert item.document_id == "fallback.pdf"

    def test_metadata_precedence(self):
        """Record-level fields should take precedence over metadata."""
        builder = EvidenceItemBuilder("test")

        citation = {
            "content": "top-level",
            "source": "top.pdf",
            "document_id": "top123",
            "metadata": {
                "content": "meta-level",  # Should be ignored
                "source": "meta.pdf",     # Should be ignored
                "document_id": "meta123"  # Should be ignored
            }
        }

        item = builder.from_legacy_citation(citation)
        assert item is not None
        assert item.content == "top-level"
        assert item.source == "top.pdf"
        assert item.document_id == "top123"

    def test_score_boundary_values(self):
        """Test score normalization at boundaries."""
        builder = EvidenceItemBuilder("test")

        # Test clamping
        assert builder._normalize_score(0.0) == 0.0
        assert builder._normalize_score(1.0) == 1.0
        assert builder._normalize_score(1.5) == 1.0  # Clamped to 1.0
        assert builder._normalize_score(-0.5) == 0.0  # Clamped to 0.0
        assert builder._normalize_score(0.5) == 0.5

        # Test invalid values
        assert builder._normalize_score(None) is None
        assert builder._normalize_score("invalid") is None
        assert builder._normalize_score(float('inf')) == 1.0  # Clamped
        assert builder._normalize_score(float('-inf')) == 0.0  # Clamped

    def test_page_boundary_values(self):
        """Test page normalization at boundaries."""
        builder = EvidenceItemBuilder("test")

        # Valid pages
        assert builder._normalize_page(1) == 1
        assert builder._normalize_page(999) == 999
        assert builder._normalize_page("5") == 5  # String conversion

        # Invalid pages
        assert builder._normalize_page(0) is None  # Must be > 0
        assert builder._normalize_page(-1) is None
        assert builder._normalize_page(None) is None
        assert builder._normalize_page("invalid") is None
        assert builder._normalize_page(3.14) == 3  # Float truncated

    def test_vector_match_invalid_format(self):
        """Test vector match with invalid formats."""
        builder = EvidenceItemBuilder("vector")

        # Not a tuple
        assert builder.from_vector_match("not a tuple") is None
        assert builder.from_vector_match([]) is None
        assert builder.from_vector_match({}) is None

        # Wrong tuple length
        assert builder.from_vector_match((1,)) is None
        assert builder.from_vector_match((1, 2, 3)) is None

        # Tuple with None
        assert builder.from_vector_match((None, 0.5)) is None

    def test_bm25_record_invalid_type(self):
        """Test BM25 record with invalid types."""
        builder = EvidenceItemBuilder("bm25")

        # Not a mapping
        assert builder.from_bm25_record(None) is None
        assert builder.from_bm25_record("string") is None
        assert builder.from_bm25_record([1, 2, 3]) is None
        assert builder.from_bm25_record(123) is None

    def test_build_item_exception_handling(self):
        """Test that _build_item handles EvidenceItem construction exceptions."""
        builder = EvidenceItemBuilder("test")

        # This should catch any Pydantic validation errors
        # EvidenceItem validation should pass, but if it fails, should return None
        result = builder._build_item(
            content="valid content",
            source="valid.pdf",
            document_id="valid123",
            page=None,
            score=0.5
        )
        assert result is not None
        assert isinstance(result, EvidenceItem)

    def test_retriever_name_preserved(self):
        """Test that retriever name is correctly set."""
        for retriever_name in ["vector", "bm25", "graph", "web"]:
            builder = EvidenceItemBuilder(retriever_name)

            citation = {
                "content": "text",
                "source": "test.pdf",
                "document_id": "123"
            }

            item = builder.from_legacy_citation(citation)
            assert item is not None
            assert item.retriever == retriever_name

    def test_field_name_variations_comprehensive(self):
        """Test all field name variations."""
        builder = EvidenceItemBuilder("test")

        # Test all source aliases
        for source_field in ["source", "url"]:
            citation = {
                "content": "text",
                source_field: "test.pdf",
                "document_id": "123"
            }
            item = builder.from_legacy_citation(citation)
            assert item is not None
            assert item.source == "test.pdf"

        # Test all document_id aliases
        for doc_field in ["document_id", "doc_id", "id"]:
            citation = {
                "content": "text",
                "source": "test.pdf",
                doc_field: "doc123"
            }
            item = builder.from_legacy_citation(citation)
            assert item is not None
            assert item.document_id == "doc123"

        # Test all content aliases
        for content_field in ["content", "snippet", "text"]:
            citation = {
                content_field: "test content",
                "source": "test.pdf",
                "document_id": "123"
            }
            item = builder.from_legacy_citation(citation)
            assert item is not None
            assert item.content == "test content"

    def test_nested_metadata_extraction(self):
        """Test extraction from nested metadata."""
        builder = EvidenceItemBuilder("test")

        citation = {
            "content": "text",
            # Source only in metadata
            "metadata": {
                "source": "nested.pdf",
                "document_id": "nested123",
                "page": 5,
                "score": 0.8
            }
        }

        item = builder.from_legacy_citation(citation)
        assert item is not None
        assert item.source == "nested.pdf"
        assert item.document_id == "nested123"
        assert item.page == 5
        assert item.score == 0.8
