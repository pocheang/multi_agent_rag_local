"""Streaming query processing.

This module provides backward compatibility for the streaming API.
All implementation has been moved to app/graph/streaming/ submodules.
"""

from app.graph.streaming import encode_sse, run_query_stream

# Backward compatibility exports
__all__ = ["run_query_stream", "encode_sse"]
