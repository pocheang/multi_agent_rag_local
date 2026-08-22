"""
QueryMind System Custom Exception Hierarchy

This module defines a comprehensive exception hierarchy for the RAG system,
providing semantic, business-context-aware error handling.

Exception Hierarchy:
    RAGBaseException
    ├── RetrievalException
    │   ├── VectorStoreException
    │   ├── BM25Exception
    │   ├── RerankerException
    │   └── GraphRetrievalException
    ├── AgentException
    │   ├── RouterAgentException
    │   ├── SynthesisAgentException
    │   └── WebResearchException
    ├── AuthException
    │   ├── InvalidCredentialsException
    │   ├── SessionExpiredException
    │   └── InsufficientPermissionsException
    ├── IngestionException
    │   ├── OCRException
    │   ├── PDFProcessingException
    │   └── ChunkingException
    ├── ConfigurationException
    ├── ResourceUnavailableException
    └── QuotaExceededException

Usage Example:
    try:
        results = vector_store.search(query)
    except VectorStoreException as e:
        logger.error(f"Vector store failed: {e.message}", extra=e.details)
        # Fallback to BM25 only
"""

from typing import Any


class RAGBaseException(Exception):
    """
    Base exception for all RAG system errors.

    All custom exceptions inherit from this class, enabling catch-all
    error handling while preserving specific exception types.

    Attributes:
        message: Human-readable error description
        details: Additional context (user_id, query, etc.)
    """

    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message)
        self.message = message
        self.details = details or {}

    def __str__(self) -> str:
        if self.details:
            detail_str = ", ".join(f"{k}={v}" for k, v in self.details.items())
            return f"{self.message} [{detail_str}]"
        return self.message


# ============================================================================
# Retrieval Layer Exceptions
# ============================================================================


class RetrievalException(RAGBaseException):
    """Base class for all retrieval-related exceptions."""

    pass


class VectorStoreException(RetrievalException):
    """
    Vector database operation failed.

    Examples:
        - ChromaDB connection timeout
        - Collection not found
        - Embedding dimension mismatch
    """

    pass


class BM25Exception(RetrievalException):
    """
    BM25 sparse retrieval failed.

    Examples:
        - Corpus store file corrupted
        - Index rebuild required
        - Tokenization error
    """

    pass


class RerankerException(RetrievalException):
    """
    Cross-encoder reranking failed.

    Examples:
        - Model not loaded (optional dependency)
        - Input exceeds max sequence length
        - CUDA out of memory
    """

    pass


class GraphRetrievalException(RetrievalException):
    """
    Knowledge graph retrieval failed.

    Examples:
        - Neo4j connection refused
        - Cypher query syntax error
        - Graph database timeout
    """

    pass


# ============================================================================
# Agent Layer Exceptions
# ============================================================================


class AgentException(RAGBaseException):
    """Base class for all agent execution exceptions."""

    pass


class RouterAgentException(AgentException):
    """
    Router agent failed to classify query intent.

    Examples:
        - LLM API timeout
        - Invalid classification output
        - Ambiguous routing decision
    """

    pass


class SynthesisAgentException(AgentException):
    """
    Synthesis agent failed to generate final answer.

    Examples:
        - LLM refusal (safety filter)
        - Citation grounding failure
        - Output format invalid
    """

    pass


class WebResearchException(AgentException):
    """
    Web research agent failed to fetch external information.

    Examples:
        - DuckDuckGo search API rate limit
        - All URLs in blocked domain list
        - Network connection failure
    """

    pass


# ============================================================================
# Authentication & Authorization Exceptions
# ============================================================================


class AuthException(RAGBaseException):
    """Base class for authentication and authorization errors."""

    pass


class InvalidCredentialsException(AuthException):
    """
    User credentials are invalid.

    Examples:
        - Wrong password
        - User not found
        - Token signature mismatch
    """

    pass


class SessionExpiredException(AuthException):
    """
    User session has expired.

    Examples:
        - JWT token past exp claim
        - Session file deleted
        - Forced logout by admin
    """

    pass


class InsufficientPermissionsException(AuthException):
    """
    User lacks required permissions for operation.

    Examples:
        - Non-admin accessing admin endpoint
        - User trying to access another user's documents
        - Role-based access control (RBAC) denial
    """

    pass


# ============================================================================
# Document Ingestion Exceptions
# ============================================================================


class IngestionException(RAGBaseException):
    """Base class for document processing exceptions."""

    pass


class OCRException(IngestionException):
    """
    OCR processing failed.

    Examples:
        - Tesseract binary not found
        - Image format unsupported
        - OCR confidence too low
    """

    pass


class PDFProcessingException(IngestionException):
    """
    PDF parsing or extraction failed.

    Examples:
        - Encrypted PDF without password
        - Corrupted PDF structure
        - PyPDF extraction error
    """

    pass


class ChunkingException(IngestionException):
    """
    Document chunking strategy failed.

    Examples:
        - Text too short to chunk
        - Parent-child relationship invalid
        - Chunk size exceeds embedding model limit
    """

    pass


# ============================================================================
# System & Resource Exceptions
# ============================================================================


class ConfigurationException(RAGBaseException):
    """
    System configuration is invalid or missing.

    Examples:
        - Missing required environment variable
        - Invalid model backend selection
        - Conflicting settings (e.g., reranker enabled but no model)
    """

    pass


class ResourceUnavailableException(RAGBaseException):
    """
    External resource is unavailable.

    Examples:
        - Redis connection refused
        - Neo4j database offline
        - LLM API endpoint unreachable
    """

    pass


class QuotaExceededException(RAGBaseException):
    """
    User or system quota exceeded.

    Examples:
        - API rate limit hit
        - Max queries per day reached
        - Storage quota full
    """

    pass


# ============================================================================
# Utility Functions
# ============================================================================


def wrap_external_exception(
    exc: Exception, custom_exc_class: type[RAGBaseException], message: str, **details
) -> RAGBaseException:
    """
    Convert a generic exception into a custom RAG exception.

    Args:
        exc: Original exception from library/external code
        custom_exc_class: Target custom exception class
        message: Human-readable error message
        **details: Additional context (key-value pairs)

    Returns:
        Instance of custom_exc_class with original exception preserved

    Example:
        try:
            chromadb.get_collection("docs")
        except Exception as e:
            raise wrap_external_exception(
                e, VectorStoreException,
                "Failed to access vector store collection",
                collection="docs",
                operation="get"
            ) from e
    """
    return custom_exc_class(message=message, details=details)
