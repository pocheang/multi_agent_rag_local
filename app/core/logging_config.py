"""
Structured Logging Configuration for QueryMind System.

This module configures structlog for production-grade structured logging
with JSON output, context propagation, and performance tracking.
"""

import logging
import sys
from typing import Any

import structlog


def configure_structured_logging(
    log_level: str = "INFO",
    json_output: bool = True,
    include_timestamp: bool = True,
) -> None:
    """
    Configure structlog for the application.

    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: If True, output JSON format; otherwise human-readable
        include_timestamp: Whether to include timestamps in logs
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, log_level.upper(), logging.INFO),
    )

    # Determine processors based on output format
    if json_output:
        processors = [
            # Add context from thread-local storage
            structlog.contextvars.merge_contextvars,
            # Add log level
            structlog.stdlib.add_log_level,
            # Add logger name
            structlog.stdlib.add_logger_name,
            # Add timestamp
            structlog.processors.TimeStamper(fmt="iso") if include_timestamp else lambda _, __, event_dict: event_dict,
            # Format stack traces
            structlog.processors.format_exc_info,
            # Render to JSON
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Human-readable console output (for development)
        processors = [
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso") if include_timestamp else lambda _, __, event_dict: event_dict,
            structlog.processors.format_exc_info,
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    # Configure structlog
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """
    Get a structured logger instance.

    Args:
        name: Logger name (typically __name__)

    Returns:
        Structured logger with context binding support
    """
    return structlog.get_logger(name)


# Context managers for request tracking
class LogContext:
    """Context manager for adding temporary log context."""

    def __init__(self, **kwargs: Any):
        self.context = kwargs
        self.token = None

    def __enter__(self):
        self.token = structlog.contextvars.bind_contextvars(**self.context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        structlog.contextvars.unbind_contextvars(*self.context.keys())


def bind_context(**kwargs: Any) -> None:
    """
    Bind context variables that will be included in all subsequent logs.

    Example:
        bind_context(user_id="user_123", request_id="req_456")
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def unbind_context(*keys: str) -> None:
    """
    Unbind context variables.

    Example:
        unbind_context("user_id", "request_id")
    """
    structlog.contextvars.unbind_contextvars(*keys)


def clear_context() -> None:
    """Clear all context variables."""
    structlog.contextvars.clear_contextvars()


# Example usage patterns
"""
# Basic logging
logger = get_logger(__name__)
logger.info("user_query_received", query="What is Docker?", user_id="user_123")

# With context binding
bind_context(request_id="req_456", user_id="user_123")
logger.info("processing_query", query="What is Docker?")
logger.info("query_routed", route="vector")
clear_context()

# With context manager
with LogContext(execution_id="exec_789", agent="RouterAgent"):
    logger.info("agent_started")
    logger.info("agent_completed", duration_ms=450)

# Exception logging
try:
    result = risky_operation()
except Exception as e:
    logger.exception("operation_failed", operation="risky_operation")
"""
