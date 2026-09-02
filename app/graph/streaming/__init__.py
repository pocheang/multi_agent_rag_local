"""Streaming components for query processing."""

from app.graph.streaming.sse_encoder import encode_sse
from app.services.query.intent import is_casual_chat_query


def run_query_stream(*args, **kwargs):
    # Retained import alias only; public API/SSE uses typed Engine streaming.
    from app.graph.streaming import stream_processor

    stream_processor.is_casual_chat_query = is_casual_chat_query
    return stream_processor.run_query_stream(*args, **kwargs)


__all__ = [
    "encode_sse",
    "run_query_stream",
    "is_casual_chat_query",
]
