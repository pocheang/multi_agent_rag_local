"""Tests for MultiModalRetriever."""

from unittest.mock import MagicMock, patch

import pytest

from app.retrievers.multimodal_retriever import MultiModalRetriever, RetrievalResult


@pytest.fixture
def retriever():
    """Create MultiModalRetriever instance."""
    return MultiModalRetriever()


@pytest.fixture
def sample_text_results():
    """Create sample text retrieval results."""
    return [
        RetrievalResult(
            id="text_1",
            content="Text content 1",
            score=0.9,
            modality="text",
            doc_id="doc_1",
            page_number=1,
            metadata={},
        ),
        RetrievalResult(
            id="text_2",
            content="Text content 2",
            score=0.8,
            modality="text",
            doc_id="doc_1",
            page_number=2,
            metadata={},
        ),
    ]


@pytest.fixture
def sample_image_results():
    """Create sample image retrieval results."""
    return [
        RetrievalResult(
            id="img_1",
            content="Image description 1",
            score=0.85,
            modality="image",
            doc_id="doc_1",
            page_number=1,
            metadata={},
        ),
    ]


@pytest.fixture
def sample_table_results():
    """Create sample table retrieval results."""
    return [
        RetrievalResult(
            id="tbl_1",
            content="Table summary 1",
            score=0.75,
            modality="table",
            doc_id="doc_1",
            page_number=3,
            metadata={},
        ),
    ]


class TestMultiModalRetriever:
    """Test MultiModalRetriever functionality."""

    @pytest.mark.asyncio
    async def test_retrieve_single_modality(self, retriever, sample_text_results):
        """Test retrieval with single modality."""
        async def mock_retrieve_text(q, k, **kw):
            return sample_text_results

        retriever._retrieve_text = mock_retrieve_text

        results = await retriever.retrieve("test query", modalities=["text"], top_k=5)

        assert len(results) > 0
        assert all(r.modality == "text" for r in results)

    @pytest.mark.asyncio
    async def test_retrieve_multiple_modalities(
        self, retriever, sample_text_results, sample_image_results
    ):
        """Test retrieval across multiple modalities."""
        async def mock_retrieve_text(q, k, **kw):
            return sample_text_results
        async def mock_retrieve_images(q, k, **kw):
            return sample_image_results
        async def mock_retrieve_tables(q, k, **kw):
            return []
        async def mock_retrieve_charts(q, k, **kw):
            return []

        retriever._retrieve_text = mock_retrieve_text
        retriever._retrieve_images = mock_retrieve_images
        retriever._retrieve_tables = mock_retrieve_tables
        retriever._retrieve_charts = mock_retrieve_charts

        results = await retriever.retrieve(
            "test query", modalities=["text", "image"], top_k=5
        )

        assert len(results) > 0
        modalities = {r.modality for r in results}
        assert "text" in modalities or "image" in modalities

    @pytest.mark.asyncio
    async def test_retrieve_default_modalities(self, retriever):
        """Test retrieval with default modalities."""
        async def mock_empty(q, k, **kw):
            return []

        retriever._retrieve_text = mock_empty
        retriever._retrieve_images = mock_empty
        retriever._retrieve_tables = mock_empty
        retriever._retrieve_charts = mock_empty

        results = await retriever.retrieve("test query", top_k=5)

        # Should not error even with empty results
        assert isinstance(results, list)

    def test_reciprocal_rank_fusion(
        self, retriever, sample_text_results, sample_image_results
    ):
        """Test RRF fusion algorithm."""
        results_by_modality = [sample_text_results, sample_image_results]

        fused = retriever._reciprocal_rank_fusion(results_by_modality, top_k=5)

        assert len(fused) <= 5
        assert all(isinstance(r, RetrievalResult) for r in fused)
        # Results should be sorted by RRF score
        scores = [r.score for r in fused]
        assert scores == sorted(scores, reverse=True)

    def test_reciprocal_rank_fusion_deduplication(self, retriever, sample_text_results):
        """Test RRF deduplicates results with same ID."""
        # Duplicate results across modalities
        results_by_modality = [sample_text_results, sample_text_results]

        fused = retriever._reciprocal_rank_fusion(results_by_modality, top_k=5)

        # Should deduplicate based on ID
        ids = [r.id for r in fused]
        assert len(ids) == len(set(ids))  # All unique

    def test_weighted_fusion(
        self, retriever, sample_text_results, sample_image_results
    ):
        """Test weighted fusion algorithm."""
        results_by_modality = [sample_text_results, sample_image_results]

        fused = retriever._weighted_fusion(results_by_modality, top_k=5)

        assert len(fused) <= 5
        assert all(isinstance(r, RetrievalResult) for r in fused)
        # Results should be sorted by weighted score
        scores = [r.score for r in fused]
        assert scores == sorted(scores, reverse=True)

    def test_weighted_fusion_respects_weights(self, retriever):
        """Test weighted fusion applies correct weights."""
        # High-scoring text result
        text_results = [
            RetrievalResult(
                id="text_1",
                content="Text",
                score=0.9,
                modality="text",
                doc_id="doc_1",
                page_number=1,
                metadata={},
            )
        ]

        # Lower-scoring image result
        image_results = [
            RetrievalResult(
                id="img_1",
                content="Image",
                score=0.5,
                modality="image",
                doc_id="doc_1",
                page_number=1,
                metadata={},
            )
        ]

        results_by_modality = [text_results, image_results]

        # With text_weight=0.4, image_weight=0.3
        # Text: 0.9 * 0.4 = 0.36
        # Image: 0.5 * 0.3 = 0.15
        # Text should rank higher
        fused = retriever._weighted_fusion(results_by_modality, top_k=5)

        assert fused[0].modality == "text"

    @pytest.mark.asyncio
    async def test_retrieve_text(self, retriever):
        """Test text retrieval."""
        with patch("app.retrievers.multimodal_retriever.get_chroma_client") as mock_get_client:
            mock_collection = MagicMock()
            mock_collection.query.return_value = {
                "ids": [["text_1", "text_2"]],
                "documents": [["Doc 1", "Doc 2"]],
                "metadatas": [[{"doc_id": "doc_1", "page_number": 1}, {"doc_id": "doc_1", "page_number": 2}]],
                "distances": [[0.1, 0.2]],
            }

            mock_client = MagicMock()
            mock_client.get_collection.return_value = mock_collection
            mock_get_client.return_value = mock_client

            results = await retriever._retrieve_text("test query", top_k=5)

            assert len(results) == 2
            assert results[0].id == "text_1"
            assert results[0].modality == "text"
            assert results[0].content == "Doc 1"

    @pytest.mark.asyncio
    async def test_retrieve_images_collection_not_found(self, retriever):
        """Test image retrieval when collection doesn't exist."""
        with patch("app.retrievers.multimodal_retriever.get_chroma_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_collection.side_effect = Exception("Collection not found")
            mock_get_client.return_value = mock_client

            results = await retriever._retrieve_images("test query", top_k=5)

            # Should return empty list, not raise error
            assert results == []

    @pytest.mark.asyncio
    async def test_retrieve_by_doc_id(self, retriever):
        """Test retrieving all content for a document."""
        with patch("app.retrievers.multimodal_retriever.get_chroma_client") as mock_get_client:
            mock_collection = MagicMock()
            mock_collection.get.return_value = {
                "ids": ["text_1"],
                "documents": ["Content 1"],
                "metadatas": [{"doc_id": "doc_123", "page_number": 1}],
            }

            mock_client = MagicMock()
            mock_client.get_collection.return_value = mock_collection
            mock_get_client.return_value = mock_client

            results = await retriever.retrieve_by_doc_id("doc_123", modalities=["text"])

            assert "text" in results
            assert len(results["text"]) == 1
            assert results["text"][0].doc_id == "doc_123"

    @pytest.mark.asyncio
    async def test_retrieve_by_doc_id_error_handling(self, retriever):
        """Test retrieve_by_doc_id handles errors gracefully."""
        with patch("app.retrievers.multimodal_retriever.get_chroma_client") as mock_get_client:
            mock_client = MagicMock()
            mock_client.get_collection.side_effect = Exception("Collection error")
            mock_get_client.return_value = mock_client

            results = await retriever.retrieve_by_doc_id("doc_123", modalities=["text"])

            # Should return empty results, not raise
            assert "text" in results
            assert results["text"] == []


class TestRetrievalResult:
    """Test RetrievalResult data model."""

    def test_retrieval_result_creation(self):
        """Test creating RetrievalResult."""
        result = RetrievalResult(
            id="test_1",
            content="Test content",
            score=0.95,
            modality="text",
            doc_id="doc_123",
            page_number=1,
            metadata={"key": "value"},
        )

        assert result.id == "test_1"
        assert result.content == "Test content"
        assert result.score == 0.95
        assert result.modality == "text"
        assert result.doc_id == "doc_123"
        assert result.page_number == 1
        assert result.metadata == {"key": "value"}

    def test_is_multimodal_property(self):
        """Test is_multimodal property."""
        text_result = RetrievalResult(
            id="test_1",
            content="Text",
            score=0.9,
            modality="text",
            doc_id="doc_1",
            page_number=1,
            metadata={},
        )
        assert text_result.is_multimodal is False

        image_result = RetrievalResult(
            id="test_2",
            content="Image",
            score=0.9,
            modality="image",
            doc_id="doc_1",
            page_number=1,
            metadata={},
        )
        assert image_result.is_multimodal is True

        table_result = RetrievalResult(
            id="test_3",
            content="Table",
            score=0.9,
            modality="table",
            doc_id="doc_1",
            page_number=1,
            metadata={},
        )
        assert table_result.is_multimodal is True
