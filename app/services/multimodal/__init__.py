"""Multi-modal document processing services.

Concrete processors are loaded lazily so installations that do not enable the
optional ``multimodal`` dependency extra can still import the service package.
"""

from typing import Any


def __getattr__(name: str) -> Any:
    if name == "ChartAnalyzer":
        from app.services.multimodal.chart_analyzer import ChartAnalyzer

        return ChartAnalyzer
    if name == "ImageProcessor":
        from app.services.multimodal.image_processor import ImageProcessor

        return ImageProcessor
    if name == "SmartChunker":
        from app.services.multimodal.smart_chunker import SmartChunker

        return SmartChunker
    if name == "TableExtractor":
        from app.services.multimodal.table_extractor import TableExtractor

        return TableExtractor
    raise AttributeError(name)

__all__ = [
    "ImageProcessor",
    "TableExtractor",
    "ChartAnalyzer",
    "SmartChunker",
]
