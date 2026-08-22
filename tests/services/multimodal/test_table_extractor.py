"""Tests for TableExtractor service."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pandas as pd
import pytest

from app.services.multimodal.models import TableContent
from app.services.multimodal.table_extractor import TableExtractor


@pytest.fixture
def table_extractor():
    """Create TableExtractor instance."""
    return TableExtractor()


@pytest.fixture
def sample_dataframe():
    """Create sample DataFrame."""
    return pd.DataFrame(
        {
            "Name": ["Alice", "Bob", "Charlie"],
            "Age": [25, 30, 35],
            "City": ["New York", "London", "Paris"],
        }
    )


@pytest.fixture
def sample_table_content(sample_dataframe):
    """Create sample TableContent."""
    return TableContent(
        table_id="tbl_test123",
        doc_id="doc_123",
        page_number=1,
        headers=sample_dataframe.columns.tolist(),
        rows=sample_dataframe.values.tolist(),
        summary="Table with 3 rows and 3 columns.",
        metadata={"num_rows": 3, "num_cols": 3},
    )


class TestTableExtractor:
    """Test TableExtractor functionality."""

    @pytest.mark.asyncio
    async def test_extract_tables_not_found(self, table_extractor):
        """Test extraction with non-existent PDF."""
        with pytest.raises(FileNotFoundError):
            await table_extractor.extract_tables_from_pdf("nonexistent.pdf", "doc_123")

    def test_generate_table_id(self, table_extractor):
        """Test table ID generation."""
        table_id = table_extractor._generate_table_id("doc_123", 1, 0)
        assert table_id.startswith("tbl_")
        assert len(table_id) == 16  # tbl_ + 12 chars

        # Same inputs should generate same ID
        table_id2 = table_extractor._generate_table_id("doc_123", 1, 0)
        assert table_id == table_id2

    def test_generate_table_summary(self, table_extractor, sample_dataframe):
        """Test table summary generation."""
        summary = table_extractor._generate_table_summary(sample_dataframe)

        assert "3 rows" in summary
        assert "3 columns" in summary
        assert "Name" in summary
        assert "Age" in summary
        assert "City" in summary

    def test_generate_table_summary_with_numeric_stats(self, table_extractor):
        """Test table summary with numeric column statistics."""
        df = pd.DataFrame(
            {
                "Product": ["A", "B", "C"],
                "Price": [10.5, 20.0, 15.75],
                "Quantity": [100, 200, 150],
            }
        )

        summary = table_extractor._generate_table_summary(df)

        assert "3 rows" in summary
        assert "Price" in summary
        assert "Quantity" in summary
        assert "avg:" in summary.lower()

    def test_parse_table_to_dataframe(self, table_extractor, sample_table_content):
        """Test converting TableContent to DataFrame."""
        df = table_extractor.parse_table_to_dataframe(sample_table_content)

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 3
        assert list(df.columns) == ["Name", "Age", "City"]
        assert df.iloc[0]["Name"] == "Alice"

    def test_format_table_as_markdown(self, table_extractor, sample_table_content):
        """Test markdown formatting."""
        markdown = table_extractor.format_table_as_markdown(sample_table_content)

        assert "Name" in markdown
        assert "Alice" in markdown
        assert "|" in markdown  # Markdown table separator

    def test_format_table_as_text(self, table_extractor, sample_table_content):
        """Test text formatting."""
        text = table_extractor.format_table_as_text(sample_table_content, max_rows=2)

        assert "Name | Age | City" in text
        assert "Alice" in text
        assert "Bob" in text
        # Charlie should not be included (max_rows=2)
        assert "more rows" in text

    def test_format_table_as_text_full(self, table_extractor, sample_table_content):
        """Test text formatting with all rows."""
        text = table_extractor.format_table_as_text(sample_table_content, max_rows=10)

        assert "Alice" in text
        assert "Bob" in text
        assert "Charlie" in text
        assert "more rows" not in text

    @pytest.mark.asyncio
    async def test_index_table(self, table_extractor, sample_table_content):
        """Test table indexing."""
        with patch("app.services.multimodal.table_extractor.get_chroma_client") as mock_get_client:
            mock_collection = MagicMock()
            mock_client = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_get_client.return_value = mock_client

            await table_extractor.index_table(sample_table_content)

            mock_collection.add.assert_called_once()
            call_args = mock_collection.add.call_args

            # Verify indexed content includes summary and table data
            indexed_text = call_args.kwargs["documents"][0]
            assert sample_table_content.summary in indexed_text
            assert "Name" in indexed_text

    @pytest.mark.asyncio
    async def test_extract_tables_batch(self, table_extractor):
        """Test batch table extraction."""
        # Mock the extract method
        mock_tables = [
            TableContent(
                table_id="tbl_1",
                doc_id="doc_1",
                page_number=1,
                headers=["A", "B"],
                rows=[[1, 2]],
                summary="Test table",
            )
        ]

        table_extractor.extract_tables_from_pdf = AsyncMock(return_value=mock_tables)

        results = await table_extractor.extract_tables_batch(
            ["doc1.pdf", "doc2.pdf"], ["doc_1", "doc_2"]
        )

        assert "doc_1" in results
        assert "doc_2" in results
        assert len(results["doc_1"]) == 1

    @pytest.mark.asyncio
    async def test_extract_tables_batch_error_handling(self, table_extractor):
        """Test batch extraction handles errors."""
        # Mock one success, one failure
        async def mock_extract(pdf_path, doc_id):
            if "bad" in str(pdf_path):
                raise Exception("PDF error")
            return []

        table_extractor.extract_tables_from_pdf = mock_extract

        results = await table_extractor.extract_tables_batch(
            ["good.pdf", "bad.pdf"], ["doc_1", "doc_2"]
        )

        assert "doc_1" in results
        assert "doc_2" in results
        assert results["doc_2"] == []  # Error case returns empty list

    @pytest.mark.asyncio
    async def test_extract_tables_batch_length_mismatch(self, table_extractor):
        """Test batch extraction with mismatched input lengths."""
        with pytest.raises(ValueError):
            await table_extractor.extract_tables_batch(
                ["doc1.pdf", "doc2.pdf"], ["doc_1"]  # Mismatch
            )


class TestTableContentModel:
    """Test TableContent data model."""

    def test_table_content_creation(self):
        """Test creating TableContent."""
        table = TableContent(
            table_id="tbl_123",
            doc_id="doc_456",
            page_number=2,
            headers=["Col1", "Col2"],
            rows=[[1, 2], [3, 4]],
            summary="Test table",
            bbox=(0, 0, 100, 100),
        )

        assert table.table_id == "tbl_123"
        assert table.doc_id == "doc_456"
        assert table.page_number == 2
        assert table.headers == ["Col1", "Col2"]
        assert len(table.rows) == 2
        assert table.summary == "Test table"
        assert table.bbox == (0, 0, 100, 100)

    def test_table_content_defaults(self):
        """Test TableContent with defaults."""
        table = TableContent(
            table_id="tbl_123",
            doc_id="doc_456",
            page_number=1,
            headers=["A"],
            rows=[[1]],
            summary="Test",
        )

        assert table.bbox is None
        assert isinstance(table.metadata, dict)
