"""
Query helper functions for the QueryMind API.
"""

import json
from typing import Any

from fastapi.responses import StreamingResponse


async def _wrap_sse_generator(generator: Any, append_terminal_event: bool):
    if hasattr(generator, "__aiter__"):
        async for chunk in generator:
            yield chunk
    else:
        for chunk in generator:
            yield chunk
    if append_terminal_event:
        yield f"data: {json.dumps({'type': 'stream_end'})}\n\n"


def _sse_response(generator: Any, *, append_terminal_event: bool = False) -> StreamingResponse:
    """Create a Server-Sent Events streaming response."""
    return StreamingResponse(
        _wrap_sse_generator(generator, append_terminal_event),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


