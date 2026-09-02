"""Chart analysis service for multi-modal RAG."""

import asyncio
import base64
import hashlib
import logging
from typing import Any

from app.core.config import get_settings
from app.services.multimodal.models import ChartContent, ImageContent

logger = logging.getLogger(__name__)


class ChartAnalyzer:
    """Analyze charts and graphs from documents."""

    def __init__(self):
        self.settings = get_settings()
        self.vision_model = getattr(self.settings, "vision_model", "gpt-4-vision-preview")

        # Chart type keywords for detection
        self.chart_keywords = {
            "bar": ["bar chart", "bar graph", "column chart", "histogram"],
            "line": ["line chart", "line graph", "trend line", "time series"],
            "pie": ["pie chart", "donut chart", "circle chart"],
            "scatter": ["scatter plot", "scatter chart", "xy plot"],
            "area": ["area chart", "area graph", "stacked area"],
            "mixed": ["combination chart", "mixed chart", "combo chart"],
        }

    async def analyze_chart(self, image: ImageContent) -> ChartContent | None:
        """Analyze a chart image and extract information.

        Args:
            image: ImageContent object (should be a chart)

        Returns:
            ChartContent object or None if not a chart
        """
        try:
            # First, detect if this is actually a chart
            is_chart = await self._is_chart_image(image)
            if not is_chart:
                logger.debug(f"Image {image.image_id} is not a chart")
                return None

            # Detect chart type
            chart_type = await self._detect_chart_type(image)

            # Generate detailed description
            description = await self._generate_chart_description(image, chart_type)

            # Extract chart title if present
            title = self._extract_title_from_description(description)

            # Try to extract data (best effort)
            chart_data = await self._extract_chart_data(image, chart_type, description)

            # Generate chart ID
            chart_id = self._generate_chart_id(image.doc_id, image.page_number, image.image_id)

            chart_content = ChartContent(
                chart_id=chart_id,
                doc_id=image.doc_id,
                page_number=image.page_number,
                chart_type=chart_type,
                title=title,
                description=description,
                data=chart_data,
                bbox=image.bbox,
                metadata={
                    "source_image_id": image.image_id,
                    "document_id": image.document_id,
                    "tenant_id": image.tenant_id,
                    "version": image.version,
                    "artifact_uri": image.artifact_uri or "",
                    "source": image.metadata.get("source", image.artifact_uri or image.doc_id),
                    "width": image.metadata.get("width", 0),
                    "height": image.metadata.get("height", 0),
                },
            )

            logger.info(f"Analyzed chart {chart_id}: {chart_type}")
            return chart_content

        except Exception:
            logger.exception(f"Error analyzing chart from {image.image_id}")
            return None

    async def _is_chart_image(self, image: ImageContent) -> bool:
        """Determine if image contains a chart/graph.

        Uses heuristics from image description or OCR text.
        """
        # Check description for chart keywords
        description_lower = image.description.lower()

        for _chart_type, keywords in self.chart_keywords.items():
            for keyword in keywords:
                if keyword in description_lower:
                    return True

        # Additional chart indicators
        chart_indicators = [
            "axis",
            "axes",
            "graph",
            "plot",
            "legend",
            "data points",
            "x-axis",
            "y-axis",
            "trend",
        ]

        indicator_count = sum(1 for indicator in chart_indicators if indicator in description_lower)

        # If 2+ indicators present, likely a chart
        return indicator_count >= 2

    async def _detect_chart_type(self, image: ImageContent) -> str:
        """Detect the type of chart.

        Args:
            image: ImageContent object

        Returns:
            Chart type string
        """
        description_lower = image.description.lower()

        # Check for explicit chart type mentions
        for chart_type, keywords in self.chart_keywords.items():
            for keyword in keywords:
                if keyword in description_lower:
                    return chart_type

        # Default to "unknown" if can't determine
        return "unknown"

    async def _generate_chart_description(self, image: ImageContent, chart_type: str) -> str:
        """Generate detailed chart description using vision model.

        Args:
            image: ImageContent object
            chart_type: Detected chart type

        Returns:
            Detailed description
        """
        try:
            # Create specialized prompt for charts
            prompt = self._create_chart_analysis_prompt(chart_type)

            # Encode image
            image_base64 = base64.b64encode(self._safe_image_bytes(image)).decode("utf-8")

            # Call vision API
            description = await self._call_vision_api(image_base64, prompt)

            return description

        except Exception:
            logger.exception("Error generating chart description")
            return image.description  # Fallback to existing description

    def _create_chart_analysis_prompt(self, chart_type: str) -> str:
        """Create specialized prompt for chart analysis."""
        base_prompt = (
            f"This is a {chart_type} chart. Provide a detailed analysis including:\n"
            "1. Chart title (if visible)\n"
            "2. Axis labels and scales\n"
            "3. Data series/categories\n"
            "4. Key trends or patterns\n"
            "5. Notable data points or outliers\n"
            "6. Overall insights\n\n"
            "Be specific and include actual values when visible."
        )
        return base_prompt

    async def _call_vision_api(self, image_base64: str, prompt: str) -> str:
        """Call vision API for chart analysis."""
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
                                    "detail": "high",  # High detail for charts
                                },
                            },
                        ],
                    }
                ],
                max_tokens=1500,  # More tokens for detailed analysis
            )

            return response.choices[0].message.content or "[No description generated]"

        except Exception:
            logger.exception("Vision API error")
            raise

    def _extract_title_from_description(self, description: str) -> str | None:
        """Extract chart title from description text."""
        # Look for title patterns
        title_patterns = [
            "title:",
            "titled",
            "titled as",
            "title is",
            "chart title:",
        ]

        lines = description.split("\n")
        for line in lines:
            line_lower = line.lower().strip()
            for pattern in title_patterns:
                if pattern in line_lower:
                    # Extract text after pattern
                    title = line.split(":", 1)[-1].strip()
                    if title:
                        # Remove quotes if present
                        title = title.strip('"').strip("'")
                        return title if len(title) > 3 else None

        return None

    async def _extract_chart_data(self, image: ImageContent, chart_type: str, description: str) -> dict[str, Any]:
        """Extract structured data from chart.

        Note: This is a best-effort extraction. For precise data,
        specialized chart parsing libraries would be needed.

        Args:
            image: ImageContent object
            chart_type: Chart type
            description: Chart description

        Returns:
            Dictionary with extracted data
        """
        data: dict[str, Any] = {
            "chart_type": chart_type,
            "extraction_method": "llm_description",
        }

        # Parse description for data points
        try:
            # Look for numerical patterns in description
            import re

            # Extract numbers and their context
            number_pattern = r"(\d+\.?\d*)\s*(percent|%|million|billion|thousand|k|m|b)?"
            matches = re.findall(number_pattern, description.lower())

            if matches:
                data["extracted_values"] = [
                    {
                        "value": float(m[0]),
                        "unit": m[1] if m[1] else None,
                    }
                    for m in matches[:20]  # Limit to 20 values
                ]

            # Extract categories/labels
            # This is simplified - real implementation would need more sophisticated parsing
            if "categories" in description.lower():
                # Try to extract category names
                category_matches = re.findall(r'"([^"]+)"', description)
                if category_matches:
                    data["categories"] = category_matches[:10]

        except Exception as e:
            logger.debug(f"Could not extract structured data: {e}")

        return data

    def _generate_chart_id(self, doc_id: str, page_num: int, image_id: str) -> str:
        """Generate unique chart ID."""
        content = f"{doc_id}:page{page_num}:chart:{image_id}"
        return f"cht_{hashlib.md5(content.encode()).hexdigest()[:12]}"

    async def analyze_charts_batch(self, images: list[ImageContent], max_concurrent: int = 3) -> list[ChartContent]:
        """Analyze multiple potential chart images.

        Args:
            images: List of ImageContent objects
            max_concurrent: Maximum concurrent analyses

        Returns:
            List of ChartContent objects (only charts)
        """
        semaphore = asyncio.Semaphore(max_concurrent)

        async def analyze_single(img: ImageContent) -> ChartContent | None:
            async with semaphore:
                return await self.analyze_chart(img)

        # Analyze all images
        results = await asyncio.gather(*[analyze_single(img) for img in images])

        # Filter out None values (non-charts)
        charts = [chart for chart in results if chart is not None]

        logger.info(f"Identified {len(charts)} charts out of {len(images)} images")
        return charts

    async def index_chart(self, chart: ChartContent, collection_name: str = "chart_descriptions") -> None:
        """Index chart content in vector database.

        Args:
            chart: ChartContent object
            collection_name: ChromaDB collection name
        """
        try:
            from app.retrievers.stores.vector import get_named_vector_store

            store = get_named_vector_store(collection_name)

            # Create text for indexing
            text_parts = []
            if chart.title:
                text_parts.append(f"Chart Title: {chart.title}")
            text_parts.append(f"Chart Type: {chart.chart_type}")
            text_parts.append(chart.description)

            # Add extracted data if available
            if "extracted_values" in chart.data:
                text_parts.append(f"Contains {len(chart.data['extracted_values'])} data points")

            text_to_index = "\n\n".join(text_parts)

            # Add to collection
            store.add_texts(
                ids=[chart.chart_id],
                texts=[text_to_index],
                metadatas=[
                    {
                        "doc_id": chart.doc_id,
                        "document_id": chart.metadata.get("document_id", chart.doc_id),
                        "tenant_id": chart.metadata.get("tenant_id", "shared"),
                        "version": chart.metadata.get("version", 1),
                        "page_number": chart.page_number,
                        "image_id": chart.metadata.get("source_image_id", ""),
                        "artifact_uri": chart.metadata.get("artifact_uri", ""),
                        "source": chart.metadata.get("source", chart.doc_id),
                        "type": "chart",
                        "chart_type": chart.chart_type,
                        "has_title": bool(chart.title),
                        "source_image_id": chart.metadata.get("source_image_id", ""),
                    }
                ],
            )

            logger.info(f"Indexed chart {chart.chart_id} in collection {collection_name}")

        except Exception:
            logger.exception(f"Error indexing chart {chart.chart_id}")
            raise

    @staticmethod
    def _safe_image_bytes(image: ImageContent) -> bytes:
        """Never allow chart VLM analysis to bypass the masking boundary."""

        if image.masked_image_data and image.metadata.get("masking_status") in {"clean", "masked"}:
            return image.masked_image_data
        raise PermissionError("chart analysis requires a privacy-approved image derivative")

    def format_chart_as_text(self, chart: ChartContent) -> str:
        """Format chart as text for display or embedding.

        Args:
            chart: ChartContent object

        Returns:
            Text representation
        """
        lines = []

        # Title
        if chart.title:
            lines.append(f"Chart: {chart.title}")
        else:
            lines.append(f"Chart (Type: {chart.chart_type})")

        lines.append("-" * 50)

        # Description
        lines.append(chart.description)

        # Data if available
        if "extracted_values" in chart.data:
            lines.append("\nExtracted Values:")
            for _i, val in enumerate(chart.data["extracted_values"][:10]):
                unit = val.get("unit", "")
                lines.append(f"  - {val['value']}{unit}")
            if len(chart.data["extracted_values"]) > 10:
                lines.append(f"  ... ({len(chart.data['extracted_values']) - 10} more)")

        return "\n".join(lines)
