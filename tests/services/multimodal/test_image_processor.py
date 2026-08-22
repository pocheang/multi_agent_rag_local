"""Tests for ImageProcessor service."""

import asyncio
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from PIL import Image

from app.services.multimodal.image_processor import ImageProcessor
from app.services.multimodal.models import ImageContent


@pytest.fixture
def image_processor():
    """Create ImageProcessor instance."""
    return ImageProcessor()


@pytest.fixture
def sample_image_bytes():
    """Create sample image bytes."""
    img = Image.new("RGB", (800, 600), color="red")
    buffer = BytesIO()
    img.save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture
def sample_image_content(sample_image_bytes):
    """Create sample ImageContent."""
    return ImageContent(
        image_id="img_test123",
        doc_id="doc_123",
        page_number=1,
        image_data=sample_image_bytes,
        description="",
        metadata={"width": 800, "height": 600, "format": "jpeg"},
    )


class TestImageProcessor:
    """Test ImageProcessor functionality."""

    @pytest.mark.asyncio
    async def test_extract_images_from_pdf_not_found(self, image_processor):
        """Test extraction with non-existent PDF."""
        with pytest.raises(FileNotFoundError):
            await image_processor.extract_images_from_pdf("nonexistent.pdf", "doc_123")

    @pytest.mark.asyncio
    async def test_generate_image_id(self, image_processor):
        """Test image ID generation."""
        image_id = image_processor._generate_image_id("doc_123", 1, 0)
        assert image_id.startswith("img_")
        assert len(image_id) == 16  # img_ + 12 chars

        # Same inputs should generate same ID
        image_id2 = image_processor._generate_image_id("doc_123", 1, 0)
        assert image_id == image_id2

    @pytest.mark.asyncio
    async def test_detect_image_type_hint(self, image_processor, sample_image_content):
        """Test image type detection."""
        # Large image (screenshot or photo)
        sample_image_content.metadata = {"width": 1200, "height": 800}
        hint = image_processor._detect_image_type_hint(sample_image_content)
        assert hint == "screenshot_or_photo"

        # Wide aspect ratio (likely chart)
        sample_image_content.metadata = {"width": 1600, "height": 400}
        hint = image_processor._detect_image_type_hint(sample_image_content)
        assert hint == "chart_or_diagram"

    @pytest.mark.asyncio
    async def test_create_vision_prompt(self, image_processor):
        """Test vision prompt creation."""
        prompt = image_processor._create_vision_prompt("chart_or_diagram")
        assert "chart" in prompt.lower()
        assert "describe" in prompt.lower()

    @pytest.mark.asyncio
    async def test_generate_description_gpt4v(self, image_processor, sample_image_content):
        """Test description generation with GPT-4V."""
        with patch("app.services.multimodal.image_processor.AsyncOpenAI") as mock_openai:
            # Mock OpenAI response
            mock_response = MagicMock()
            mock_response.choices = [MagicMock()]
            mock_response.choices[0].message.content = "A red image"

            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_openai.return_value = mock_client

            description = await image_processor.generate_description(
                sample_image_content, use_claude=False
            )

            assert description == "A red image"
            assert sample_image_content.description == "A red image"
            mock_client.chat.completions.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_description_claude(self, image_processor, sample_image_content):
        """Test description generation with Claude."""
        with patch("app.services.multimodal.image_processor.AsyncAnthropic") as mock_anthropic:
            # Mock Claude response
            mock_response = MagicMock()
            mock_content = MagicMock()
            mock_content.text = "A red square image"
            mock_response.content = [mock_content]

            mock_client = AsyncMock()
            mock_client.messages.create = AsyncMock(return_value=mock_response)
            mock_anthropic.return_value = mock_client

            description = await image_processor.generate_description(
                sample_image_content, use_claude=True
            )

            assert description == "A red square image"
            mock_client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_is_simple_image(self, image_processor, sample_image_content):
        """Test simple image detection."""
        # Small image
        sample_image_content.metadata = {"width": 400, "height": 300}
        assert image_processor._is_simple_image(sample_image_content) is True

        # Large image
        sample_image_content.metadata = {"width": 2000, "height": 1500}
        assert image_processor._is_simple_image(sample_image_content) is False

    @pytest.mark.asyncio
    async def test_process_images_batch(self, image_processor, sample_image_content):
        """Test batch image processing."""
        images = [sample_image_content]

        # Mock methods
        image_processor.generate_description = AsyncMock(return_value="Test description")
        image_processor.perform_ocr = AsyncMock(return_value="Test OCR")

        processed = await image_processor.process_images_batch(
            images,
            generate_descriptions=True,
            perform_ocr=True,
            max_concurrent=5,
        )

        assert len(processed) == 1
        assert processed[0].description == "Test description"
        assert processed[0].ocr_text == "Test OCR"

    @pytest.mark.asyncio
    async def test_process_images_batch_error_handling(
        self, image_processor, sample_image_content
    ):
        """Test batch processing handles errors gracefully."""
        images = [sample_image_content]

        # Mock methods to raise error
        image_processor.generate_description = AsyncMock(
            side_effect=Exception("API error")
        )
        image_processor.perform_ocr = AsyncMock(return_value="")

        # Should not raise, but handle error
        processed = await image_processor.process_images_batch(
            images, generate_descriptions=True, perform_ocr=True
        )

        assert len(processed) == 1
        # Description should remain empty due to error
        assert processed[0].description == ""

    @pytest.mark.asyncio
    async def test_ocr_tesseract(self, image_processor, sample_image_content):
        """Test OCR with Tesseract."""
        with patch("app.services.multimodal.image_processor.pytesseract") as mock_tesseract:
            mock_tesseract.image_to_string.return_value = "Extracted text from image"

            text = await image_processor.perform_ocr(sample_image_content)

            assert text == "Extracted text from image"
            assert sample_image_content.ocr_text == "Extracted text from image"

    @pytest.mark.asyncio
    async def test_ocr_disabled(self, image_processor, sample_image_content):
        """Test OCR when disabled."""
        image_processor.enable_ocr = False

        text = await image_processor.perform_ocr(sample_image_content)

        assert text == ""

    @pytest.mark.asyncio
    async def test_index_image(self, image_processor, sample_image_content):
        """Test image indexing."""
        with patch("app.services.multimodal.image_processor.get_chroma_client") as mock_get_client:
            sample_image_content.description = "Test image"
            sample_image_content.ocr_text = "OCR text"

            mock_collection = MagicMock()
            mock_client = MagicMock()
            mock_client.get_or_create_collection.return_value = mock_collection
            mock_get_client.return_value = mock_client

            await image_processor.index_image(sample_image_content)

            mock_collection.add.assert_called_once()
            call_args = mock_collection.add.call_args

            # Verify indexed content includes both description and OCR
            assert "Test image" in call_args.kwargs["documents"][0]
            assert "OCR text" in call_args.kwargs["documents"][0]


class TestImageContentModel:
    """Test ImageContent data model."""

    def test_image_content_creation(self, sample_image_bytes):
        """Test creating ImageContent."""
        img = ImageContent(
            image_id="img_123",
            doc_id="doc_456",
            page_number=2,
            image_data=sample_image_bytes,
            description="Test description",
            ocr_text="Test OCR",
            bbox=(0, 0, 100, 100),
        )

        assert img.image_id == "img_123"
        assert img.doc_id == "doc_456"
        assert img.page_number == 2
        assert img.description == "Test description"
        assert img.ocr_text == "Test OCR"
        assert img.bbox == (0, 0, 100, 100)

    def test_image_content_defaults(self, sample_image_bytes):
        """Test ImageContent with defaults."""
        img = ImageContent(
            image_id="img_123",
            doc_id="doc_456",
            page_number=1,
            image_data=sample_image_bytes,
            description="Test",
        )

        assert img.ocr_text is None
        assert img.bbox is None
        assert img.image_type == "unknown"
        assert isinstance(img.metadata, dict)
