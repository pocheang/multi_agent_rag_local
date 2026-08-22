"""Image processing service for multi-modal RAG."""

import asyncio
import base64
import hashlib
import logging
from io import BytesIO
from pathlib import Path
from typing import Any

import fitz  # PyMuPDF
from PIL import Image

from app.core.config import get_settings
from app.services.multimodal.models import ImageContent

logger = logging.getLogger(__name__)


class ImageProcessor:
    """Process images from documents with GPT-4V and OCR."""

    def __init__(self):
        self.settings = get_settings()
        self.vision_model = getattr(self.settings, "vision_model", "gpt-4-vision-preview")
        self.max_image_tokens = getattr(self.settings, "max_image_tokens", 1000)
        self.enable_ocr = getattr(self.settings, "enable_ocr", True)
        self.ocr_engine = getattr(self.settings, "ocr_engine", "tesseract")
        self.min_image_size = (50, 50)  # Minimum image dimensions
        self.max_image_size = (2048, 2048)  # Maximum for GPT-4V

    async def extract_images_from_pdf(self, pdf_path: str | Path, doc_id: str) -> list[ImageContent]:
        """Extract images from PDF document.

        Args:
            pdf_path: Path to PDF file
            doc_id: Document identifier

        Returns:
            List of ImageContent objects
        """
        pdf_path = Path(pdf_path)
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF not found: {pdf_path}")

        images: list[ImageContent] = []

        try:
            with fitz.open(str(pdf_path)) as doc:
                for page_num in range(len(doc)):
                    page = doc[page_num]
                    image_list = page.get_images(full=True)

                    for img_index, img_info in enumerate(image_list):
                        try:
                            xref = img_info[0]
                            base_image = doc.extract_image(xref)
                            image_bytes = base_image["image"]
                            image_ext = base_image["ext"]

                            # Load image with PIL
                            pil_image = Image.open(BytesIO(image_bytes))

                            # Filter small images (likely icons or decorations)
                            if pil_image.size[0] < self.min_image_size[0] or pil_image.size[1] < self.min_image_size[1]:
                                logger.debug(f"Skipping small image: {pil_image.size} on page {page_num + 1}")
                                continue

                            # Get image position
                            bbox = self._get_image_bbox(page, xref)

                            # Generate image ID
                            image_id = self._generate_image_id(doc_id, page_num + 1, img_index)

                            # Create ImageContent (description will be generated later)
                            image_content = ImageContent(
                                image_id=image_id,
                                doc_id=doc_id,
                                page_number=page_num + 1,
                                image_data=image_bytes,
                                description="",  # To be filled by GPT-4V
                                ocr_text=None,  # To be filled by OCR
                                bbox=bbox,
                                metadata={
                                    "format": image_ext,
                                    "width": pil_image.size[0],
                                    "height": pil_image.size[1],
                                    "mode": pil_image.mode,
                                },
                            )

                            images.append(image_content)

                        except Exception as e:
                            logger.error(f"Error extracting image {img_index} from page {page_num + 1}: {e}")
                            continue

                logger.info(f"Extracted {len(images)} images from {pdf_path.name}")

        except Exception as e:
            logger.error(f"Error processing PDF {pdf_path}: {e}", exc_info=True)
            raise

        return images

    def _get_image_bbox(self, page: Any, xref: int) -> tuple[float, float, float, float] | None:
        """Get bounding box for image on page."""
        try:
            # Get all image rectangles on the page
            img_list = page.get_image_rects(xref)
            if img_list:
                rect = img_list[0]  # First occurrence
                return (rect.x0, rect.y0, rect.width, rect.height)
        except Exception as e:
            logger.debug(f"Could not get image bbox: {e}")
        return None

    def _generate_image_id(self, doc_id: str, page_num: int, img_index: int) -> str:
        """Generate unique image ID."""
        content = f"{doc_id}:page{page_num}:img{img_index}"
        return f"img_{hashlib.md5(content.encode()).hexdigest()[:12]}"

    async def generate_description(self, image: ImageContent, use_claude: bool = False) -> str:
        """Generate image description using GPT-4V or Claude.

        Args:
            image: ImageContent object
            use_claude: Use Claude Haiku instead of GPT-4V (cheaper)

        Returns:
            Generated description
        """
        try:
            # Prepare image data
            image_base64 = base64.b64encode(image.image_data).decode("utf-8")

            # Determine image type hint from context
            image_type_hint = self._detect_image_type_hint(image)

            # Create prompt
            prompt = self._create_vision_prompt(image_type_hint)

            # Call vision API
            if use_claude:
                description = await self._call_claude_vision(image_base64, prompt)
            else:
                description = await self._call_gpt4v(image_base64, prompt)

            # Update image content
            image.description = description
            logger.info(f"Generated description for {image.image_id}: {description[:100]}...")

            return description

        except Exception as e:
            logger.error(f"Error generating description for {image.image_id}: {e}")
            return f"[Image on page {image.page_number}]"

    def _detect_image_type_hint(self, image: ImageContent) -> str:
        """Detect likely image type from metadata."""
        width = image.metadata.get("width", 0)
        height = image.metadata.get("height", 0)
        aspect_ratio = width / height if height > 0 else 1.0

        # Heuristics
        if aspect_ratio > 2.0 or aspect_ratio < 0.5:
            return "chart_or_diagram"
        elif width > 800 and height > 600:
            return "screenshot_or_photo"
        else:
            return "diagram_or_illustration"

    def _create_vision_prompt(self, image_type_hint: str) -> str:
        """Create prompt for vision model."""
        prompts = {
            "chart_or_diagram": (
                "Describe this chart or diagram in detail. "
                "Include: type of chart, axes labels, data trends, key insights, and any text visible. "
                "Be concise but comprehensive."
            ),
            "screenshot_or_photo": (
                "Describe this image in detail. "
                "Include: main subjects, context, visible text, and important details. "
                "Focus on information relevant for document understanding."
            ),
            "diagram_or_illustration": (
                "Describe this diagram or illustration. "
                "Include: components, relationships, labels, and what concept it represents. "
                "Be precise and technical."
            ),
        }
        return prompts.get(image_type_hint, prompts["diagram_or_illustration"])

    async def _call_gpt4v(self, image_base64: str, prompt: str) -> str:
        """Call GPT-4V API for image description."""
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(
                api_key=self.settings.openai_api_key,
                base_url=self.settings.openai_base_url,
            )

            response = await client.chat.completions.create(
                model=self.vision_model,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{image_base64}",
                                    "detail": "auto",
                                },
                            },
                        ],
                    }
                ],
                max_tokens=self.max_image_tokens,
            )

            return response.choices[0].message.content or "[No description generated]"

        except Exception as e:
            logger.error(f"GPT-4V API error: {e}")
            raise

    async def _call_claude_vision(self, image_base64: str, prompt: str) -> str:
        """Call Claude vision API for image description (cheaper alternative)."""
        try:
            from anthropic import AsyncAnthropic

            client = AsyncAnthropic(api_key=self.settings.anthropic_api_key)

            response = await client.messages.create(
                model="claude-3-haiku-20240307",  # Cheapest vision model
                max_tokens=self.max_image_tokens,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/jpeg",
                                    "data": image_base64,
                                },
                            },
                            {"type": "text", "text": prompt},
                        ],
                    }
                ],
            )

            return response.content[0].text if response.content else "[No description generated]"

        except Exception as e:
            logger.error(f"Claude Vision API error: {e}")
            raise

    async def perform_ocr(self, image: ImageContent) -> str:
        """Perform OCR on image to extract text.

        Args:
            image: ImageContent object

        Returns:
            Extracted text
        """
        if not self.enable_ocr:
            return ""

        try:
            pil_image = Image.open(BytesIO(image.image_data))

            if self.ocr_engine == "tesseract":
                ocr_text = await self._ocr_tesseract(pil_image)
            elif self.ocr_engine == "paddleocr":
                ocr_text = await self._ocr_paddleocr(pil_image)
            else:
                logger.warning(f"Unknown OCR engine: {self.ocr_engine}")
                return ""

            # Update image content
            image.ocr_text = ocr_text
            logger.info(f"OCR extracted {len(ocr_text)} chars from {image.image_id}")

            return ocr_text

        except Exception as e:
            logger.error(f"OCR error for {image.image_id}: {e}")
            return ""

    async def _ocr_tesseract(self, pil_image: Image.Image) -> str:
        """Perform OCR using Tesseract."""
        try:
            import pytesseract

            # Get OCR languages from config
            lang = getattr(self.settings, "ocr_languages", "eng+chi_sim")

            # Run OCR in thread pool (blocking operation)
            loop = asyncio.get_event_loop()
            text = await loop.run_in_executor(None, lambda: pytesseract.image_to_string(pil_image, lang=lang))

            return text.strip()

        except ImportError:
            logger.error("pytesseract not installed. Install with: pip install pytesseract")
            return ""
        except Exception as e:
            logger.error(f"Tesseract OCR error: {e}")
            return ""

    async def _ocr_paddleocr(self, pil_image: Image.Image) -> str:
        """Perform OCR using PaddleOCR (better for Chinese)."""
        try:
            from paddleocr import PaddleOCR

            # Initialize PaddleOCR
            ocr = PaddleOCR(use_angle_cls=True, lang="ch", show_log=False)

            # Convert PIL to numpy array
            import numpy as np

            img_array = np.array(pil_image)

            # Run OCR in thread pool
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: ocr.ocr(img_array, cls=True))

            # Extract text from result
            text_lines = []
            if result and result[0]:
                for line in result[0]:
                    if line[1]:
                        text_lines.append(line[1][0])

            return "\n".join(text_lines)

        except ImportError:
            logger.error("paddleocr not installed. Install with: pip install paddlepaddle paddleocr")
            return ""
        except Exception as e:
            logger.error(f"PaddleOCR error: {e}")
            return ""

    async def process_images_batch(
        self,
        images: list[ImageContent],
        generate_descriptions: bool = True,
        perform_ocr: bool = True,
        use_claude_for_simple: bool = True,
        max_concurrent: int = 5,
    ) -> list[ImageContent]:
        """Process multiple images concurrently.

        Args:
            images: List of ImageContent objects
            generate_descriptions: Whether to generate descriptions
            perform_ocr: Whether to perform OCR
            use_claude_for_simple: Use Claude Haiku for simple images (cheaper)
            max_concurrent: Maximum concurrent operations

        Returns:
            List of processed ImageContent objects
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def process_single(img: ImageContent) -> ImageContent:
            async with semaphore:
                try:
                    # Generate description
                    if generate_descriptions:
                        # Simple images use Claude (cheaper)
                        use_claude = use_claude_for_simple and self._is_simple_image(img)
                        await self.generate_description(img, use_claude=use_claude)

                    # Perform OCR
                    if perform_ocr:
                        await self.perform_ocr(img)

                except Exception as e:
                    logger.error(f"Error processing image {img.image_id}: {e}")

                return img

        # Process all images concurrently
        processed = await asyncio.gather(*[process_single(img) for img in images])

        logger.info(f"Batch processed {len(processed)} images")
        return processed

    def _is_simple_image(self, image: ImageContent) -> bool:
        """Determine if image is simple enough for Claude Haiku."""
        # Heuristics: small images, diagrams, simple charts
        width = image.metadata.get("width", 0)
        height = image.metadata.get("height", 0)
        total_pixels = width * height

        # Images under 500K pixels are considered simple
        return total_pixels < 500_000

    async def index_image(self, image: ImageContent, collection_name: str = "image_descriptions") -> None:
        """Index image content in vector database.

        Args:
            image: ImageContent with description
            collection_name: ChromaDB collection name
        """
        try:
            from app.retrievers.stores.chroma_store import get_chroma_client

            # Get ChromaDB client
            client = get_chroma_client()
            collection = client.get_or_create_collection(
                name=collection_name,
                metadata={"hnsw:space": "cosine"},
            )

            # Combine description and OCR text for indexing
            text_to_index = image.description
            if image.ocr_text:
                text_to_index += f"\n\nExtracted text: {image.ocr_text}"

            # Add to collection
            collection.add(
                ids=[image.image_id],
                documents=[text_to_index],
                metadatas=[
                    {
                        "doc_id": image.doc_id,
                        "page_number": image.page_number,
                        "type": "image",
                        "image_type": image.image_type,
                        "has_ocr": bool(image.ocr_text),
                        "width": image.metadata.get("width", 0),
                        "height": image.metadata.get("height", 0),
                    }
                ],
            )

            logger.info(f"Indexed image {image.image_id} in collection {collection_name}")

        except Exception as e:
            logger.error(f"Error indexing image {image.image_id}: {e}")
            raise
