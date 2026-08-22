"""
API routes for session metadata management.

POST   /api/v1/sessions/{id}/metadata       - Update session metadata
GET    /api/v1/sessions/{id}/metadata       - Get session metadata
DELETE /api/v1/sessions/{id}/metadata       - Delete session metadata
GET    /api/v1/sessions/search              - Search sessions
GET    /api/v1/sessions/tags                - Get all tags
"""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.dependencies import _require_user, _require_valid_session_id
from app.services.sessions.search import (
    SearchQuery,
    SessionSearchService,
)
from app.services.sessions.service import (
    MetadataUpdate,
    SessionCategory,
    SessionMetadata,
    get_metadata_service,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/sessions", tags=["session-metadata"])


def _metadata_service_for_user(user: dict[str, Any]):
    return get_metadata_service(str(user.get("user_id", "") or ""))


# ============================================================================
# Request/Response Models
# ============================================================================


class MetadataResponse(BaseModel):
    """Response model for session metadata."""

    session_id: str
    tags: list[str]
    category: SessionCategory | None
    description: str | None
    auto_tags: list[str]
    created_at: str
    updated_at: str
    query_count: int
    last_query_at: str | None


class UpdateMetadataRequest(BaseModel):
    """Request model for updating metadata."""

    tags: list[str] | None = Field(default=None, description="User-defined tags")
    category: SessionCategory | None = Field(default=None, description="Session category")
    description: str | None = Field(default=None, max_length=500, description="Session description")
    increment_query_count: bool = Field(default=False, description="Increment query count")


class ExtractTagsRequest(BaseModel):
    """Request model for extracting auto tags."""

    messages: list[dict[str, str]] = Field(..., description="Recent messages for tag extraction")


class SearchSessionsRequest(BaseModel):
    """Request model for session search."""

    q: str | None = Field(default=None, description="Search query text")
    tags: list[str] | None = Field(default=None, description="Match any of these tags")
    tags_all: list[str] | None = Field(default=None, description="Match all of these tags")
    category: SessionCategory | None = Field(default=None, description="Filter by category")
    created_after: str | None = Field(default=None, description="ISO datetime")
    created_before: str | None = Field(default=None, description="ISO datetime")
    updated_after: str | None = Field(default=None, description="ISO datetime")
    updated_before: str | None = Field(default=None, description="ISO datetime")
    min_queries: int | None = Field(default=None, ge=0, description="Minimum query count")
    max_queries: int | None = Field(default=None, ge=0, description="Maximum query count")
    sort_by: str = Field(default="updated_at", description="Sort field")
    sort_order: str = Field(default="desc", description="Sort order (asc/desc)")
    limit: int = Field(default=50, ge=1, le=100, description="Results limit")
    offset: int = Field(default=0, ge=0, description="Results offset")


class SearchResultResponse(BaseModel):
    """Response model for search result."""

    session_id: str
    metadata: MetadataResponse
    score: float
    matched_tags: list[str] | None


class SearchResponse(BaseModel):
    """Response model for session search."""

    results: list[SearchResultResponse]
    total: int
    limit: int
    offset: int


class TagsResponse(BaseModel):
    """Response model for all tags."""

    tags: list[str]


# ============================================================================
# Helper Functions
# ============================================================================


def _metadata_to_response(metadata: SessionMetadata) -> MetadataResponse:
    """Convert SessionMetadata to response model."""
    return MetadataResponse(
        session_id=metadata.session_id,
        tags=metadata.tags,
        category=metadata.category,
        description=metadata.description,
        auto_tags=metadata.auto_tags,
        created_at=metadata.created_at.isoformat(),
        updated_at=metadata.updated_at.isoformat(),
        query_count=metadata.query_count,
        last_query_at=metadata.last_query_at.isoformat() if metadata.last_query_at else None,
    )


# ============================================================================
# API Endpoints
# ============================================================================


@router.post("/{session_id}/metadata", response_model=MetadataResponse)
def update_session_metadata(
    session_id: str,
    request: UpdateMetadataRequest,
    user: dict[str, Any] = Depends(_require_user),
):
    """
    Update session metadata.

    Creates metadata if it doesn't exist, otherwise updates existing.
    """
    session_id = _require_valid_session_id(session_id)
    service = _metadata_service_for_user(user)

    try:
        # Check if metadata exists
        existing = service.get_metadata(session_id)

        if existing is None:
            # Create new metadata
            metadata = service.create_metadata(
                session_id=session_id,
                tags=request.tags or [],
                category=request.category,
                description=request.description,
            )
        else:
            # Update existing
            update = MetadataUpdate(
                tags=request.tags,
                category=request.category,
                description=request.description,
                increment_query_count=request.increment_query_count,
            )
            metadata = service.update_metadata(session_id, update)

        logger.info(f"Updated metadata for session {session_id}")
        return _metadata_to_response(metadata)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.exception(f"Failed to update metadata for {session_id}")
        raise HTTPException(status_code=500, detail="Failed to update metadata")


@router.get("/{session_id}/metadata", response_model=MetadataResponse)
def get_session_metadata(session_id: str, user: dict[str, Any] = Depends(_require_user)):
    """
    Get session metadata.

    Returns 404 if metadata not found.
    """
    session_id = _require_valid_session_id(session_id)
    service = _metadata_service_for_user(user)
    metadata = service.get_metadata(session_id)

    if metadata is None:
        raise HTTPException(status_code=404, detail=f"Metadata not found for session {session_id}")

    return _metadata_to_response(metadata)


@router.delete("/{session_id}/metadata")
def delete_session_metadata(session_id: str, user: dict[str, Any] = Depends(_require_user)):
    """
    Delete session metadata.

    Returns 404 if metadata not found.
    """
    session_id = _require_valid_session_id(session_id)
    service = _metadata_service_for_user(user)
    result = service.delete_metadata(session_id)

    if not result:
        raise HTTPException(status_code=404, detail=f"Metadata not found for session {session_id}")

    logger.info(f"Deleted metadata for session {session_id}")
    return {"message": "Metadata deleted successfully", "session_id": session_id}


@router.post("/{session_id}/metadata/extract-tags", response_model=MetadataResponse)
def extract_auto_tags(
    session_id: str,
    request: ExtractTagsRequest,
    user: dict[str, Any] = Depends(_require_user),
):
    """
    Extract and update automatic tags from messages.

    Requires metadata to exist for the session.
    """
    session_id = _require_valid_session_id(session_id)
    service = _metadata_service_for_user(user)

    try:
        auto_tags = service.extract_and_update_auto_tags(session_id, request.messages)
        metadata = service.get_metadata(session_id)

        logger.info(f"Extracted {len(auto_tags)} auto tags for session {session_id}")
        return _metadata_to_response(metadata)

    except KeyError:
        raise HTTPException(status_code=404, detail=f"Metadata not found for session {session_id}")
    except Exception:
        logger.exception("Failed to extract tags for %s", session_id)
        raise HTTPException(status_code=500, detail="Failed to extract tags")


@router.post("/search", response_model=SearchResponse)
def search_sessions(request: SearchSessionsRequest, user: dict[str, Any] = Depends(_require_user)):
    """
    Search and filter sessions.

    Supports text search, tag filtering, category filtering, time ranges,
    and query count ranges. Returns paginated results with relevance scores.
    """
    search_service = SessionSearchService(metadata_service=_metadata_service_for_user(user))

    try:
        # Parse datetime strings
        from datetime import datetime as dt

        created_after = dt.fromisoformat(request.created_after) if request.created_after else None
        created_before = dt.fromisoformat(request.created_before) if request.created_before else None
        updated_after = dt.fromisoformat(request.updated_after) if request.updated_after else None
        updated_before = dt.fromisoformat(request.updated_before) if request.updated_before else None

        # Build search query
        query = SearchQuery(
            q=request.q,
            tags=request.tags,
            tags_all=request.tags_all,
            category=request.category,
            created_after=created_after,
            created_before=created_before,
            updated_after=updated_after,
            updated_before=updated_before,
            min_queries=request.min_queries,
            max_queries=request.max_queries,
            sort_by=request.sort_by,
            sort_order=request.sort_order,
            limit=request.limit,
            offset=request.offset,
        )

        # Execute search
        results = search_service.search(query)
        total = search_service.count(query)

        # Convert to response
        response_results = [
            SearchResultResponse(
                session_id=result.metadata.session_id,
                metadata=_metadata_to_response(result.metadata),
                score=result.score,
                matched_tags=result.matched_tags,
            )
            for result in results
        ]

        logger.info(f"Search returned {len(results)} results (total: {total})")
        return SearchResponse(
            results=response_results,
            total=total,
            limit=request.limit,
            offset=request.offset,
        )

    except ValueError as e:
        raise HTTPException(status_code=400, detail=f"Invalid date format: {str(e)}")
    except Exception:
        logger.exception("Session metadata search failed")
        raise HTTPException(status_code=500, detail="Search failed")


@router.get("/tags", response_model=TagsResponse)
def get_all_tags(user: dict[str, Any] = Depends(_require_user)):
    """
    Get all unique tags across all sessions.

    Includes both user-defined tags and auto-extracted tags.
    """
    service = _metadata_service_for_user(user)
    tags = service.get_all_tags()

    return TagsResponse(tags=tags)


@router.get("/facets")
def get_search_facets(user: dict[str, Any] = Depends(_require_user)):
    """
    Get available facets for filtering.

    Returns categories, tags, and query count range.
    """
    search_service = SessionSearchService(metadata_service=_metadata_service_for_user(user))
    facets = search_service.get_facets()

    return facets
