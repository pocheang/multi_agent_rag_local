"""SSE (Server-Sent Events) encoder."""

import json
from typing import Any


def encode_sse(data: dict[str, Any]) -> str:
    """Encode data as SSE format."""
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
