"""
Query helper functions for the Multi-Agent Local RAG API.
"""
from typing import Any

from fastapi.responses import StreamingResponse


def _sse_response(generator: Any) -> StreamingResponse:
    """Create a Server-Sent Events streaming response."""
    return StreamingResponse(
        generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
