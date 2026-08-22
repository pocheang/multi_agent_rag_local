"""
Integration tests for session metadata and export API endpoints.

Tests the full stack: API routes -> Services -> Data models
"""

import json
from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from app.api.routes.sessions import router


@pytest.fixture
def client():
    """Create test client with sessions router."""
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router)
    client = TestClient(app)
    client.headers.update(
        {
            "X-Test-User": "session-api-test-user",
            "X-Test-User-Id": "session-api-test-user",
            "X-Test-Role": "viewer",
        }
    )
    return client


@pytest.fixture
def session_with_metadata(client):
    """Create a test session with metadata."""
    session_id = "test-session-123"

    # Create metadata
    response = client.post(
        f"/api/v1/sessions/{session_id}/metadata",
        json={
            "tags": ["test", "example"],
            "category": "research",
            "description": "Test session for API integration tests",
        },
    )
    assert response.status_code == 200

    yield session_id

    # Cleanup
    client.delete(f"/api/v1/sessions/{session_id}/metadata")


# ============================================================================
# Metadata CRUD Tests
# ============================================================================


def test_create_metadata(client):
    """Test creating new session metadata."""
    session_id = "new-session-456"

    response = client.post(
        f"/api/v1/sessions/{session_id}/metadata",
        json={
            "tags": ["python", "fastapi"],
            "category": "development",
            "description": "API development session",
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_id
    assert set(data["tags"]) == {"python", "fastapi"}
    assert data["category"] == "development"
    assert data["description"] == "API development session"
    assert data["query_count"] == 0

    # Cleanup
    client.delete(f"/api/v1/sessions/{session_id}/metadata")


def test_get_metadata(session_with_metadata, client):
    """Test retrieving session metadata."""
    response = client.get(f"/api/v1/sessions/{session_with_metadata}/metadata")

    assert response.status_code == 200
    data = response.json()
    assert data["session_id"] == session_with_metadata
    assert "test" in data["tags"]


def test_get_metadata_not_found(client):
    """Test getting non-existent metadata returns 404."""
    response = client.get("/api/v1/sessions/nonexistent/metadata")
    assert response.status_code == 404


def test_update_metadata(session_with_metadata, client):
    """Test updating existing metadata."""
    response = client.post(
        f"/api/v1/sessions/{session_with_metadata}/metadata",
        json={
            "tags": ["updated", "tags"],
            "increment_query_count": True,
        },
    )

    assert response.status_code == 200
    data = response.json()
    assert set(data["tags"]) == {"updated", "tags"}
    assert data["query_count"] == 1


def test_delete_metadata(client):
    """Test deleting session metadata."""
    session_id = "delete-test-789"

    # Create
    client.post(
        f"/api/v1/sessions/{session_id}/metadata",
        json={"tags": ["temp"]},
    )

    # Delete
    response = client.delete(f"/api/v1/sessions/{session_id}/metadata")
    assert response.status_code == 200

    # Verify deleted
    response = client.get(f"/api/v1/sessions/{session_id}/metadata")
    assert response.status_code == 404


def test_delete_metadata_not_found(client):
    """Test deleting non-existent metadata returns 404."""
    response = client.delete("/api/v1/sessions/nonexistent/metadata")
    assert response.status_code == 404


# ============================================================================
# Tag Extraction Tests
# ============================================================================


def test_extract_auto_tags(session_with_metadata, client):
    """Test automatic tag extraction from messages."""
    messages = [
        {"role": "user", "content": "How do I implement authentication in FastAPI?"},
        {"role": "assistant", "content": "You can use OAuth2 with JWT tokens..."},
        {"role": "user", "content": "What about database integration?"},
    ]

    response = client.post(
        f"/api/v1/sessions/{session_with_metadata}/metadata/extract-tags",
        json={"messages": messages},
    )

    assert response.status_code == 200
    data = response.json()
    auto_tags = data["auto_tags"]
    assert len(auto_tags) > 0
    # Should extract domain-relevant tags
    assert any(tag in ["fastapi", "authentication", "database"] for tag in auto_tags)


def test_extract_tags_session_not_found(client):
    """Test tag extraction on non-existent session returns 404."""
    response = client.post(
        "/api/v1/sessions/nonexistent/metadata/extract-tags",
        json={"messages": [{"role": "user", "content": "test"}]},
    )
    assert response.status_code == 404


# ============================================================================
# Search Tests
# ============================================================================


def test_search_by_text(client):
    """Test searching sessions by text query."""
    # Create test sessions
    sessions = [
        ("search-1", {"tags": ["python"], "description": "Python programming"}),
        ("search-2", {"tags": ["javascript"], "description": "React development"}),
        ("search-3", {"tags": ["python", "data"], "description": "Data analysis"}),
    ]

    for session_id, metadata in sessions:
        client.post(f"/api/v1/sessions/{session_id}/metadata", json=metadata)

    # Search for "python"
    response = client.post("/api/v1/sessions/search", json={"q": "python"})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    assert all("python" in r["metadata"]["tags"] or "python" in r["metadata"]["description"].lower() for r in data["results"][:2])

    # Cleanup
    for session_id, _ in sessions:
        client.delete(f"/api/v1/sessions/{session_id}/metadata")


def test_search_by_tags(client):
    """Test searching sessions by tags."""
    # Create test sessions
    client.post("/api/v1/sessions/tag-1/metadata", json={"tags": ["python", "ml"]})
    client.post("/api/v1/sessions/tag-2/metadata", json={"tags": ["python", "web"]})
    client.post("/api/v1/sessions/tag-3/metadata", json={"tags": ["javascript"]})

    # Search for sessions with "python" tag
    response = client.post("/api/v1/sessions/search", json={"tags": ["python"]})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 2
    for result in data["results"]:
        if result["session_id"] in ["tag-1", "tag-2"]:
            assert "python" in result["metadata"]["tags"]

    # Cleanup
    for i in range(1, 4):
        client.delete(f"/api/v1/sessions/tag-{i}/metadata")


def test_search_by_category(client):
    """Test searching sessions by category."""
    # Create test sessions
    client.post("/api/v1/sessions/cat-1/metadata", json={"category": "research"})
    client.post("/api/v1/sessions/cat-2/metadata", json={"category": "development"})

    # Search for research category
    response = client.post("/api/v1/sessions/search", json={"category": "research"})

    assert response.status_code == 200
    data = response.json()
    assert data["total"] >= 1
    assert any(r["metadata"]["category"] == "research" for r in data["results"])

    # Cleanup
    client.delete("/api/v1/sessions/cat-1/metadata")
    client.delete("/api/v1/sessions/cat-2/metadata")


def test_search_pagination(client):
    """Test search pagination."""
    # Create multiple sessions
    for i in range(5):
        client.post(
            f"/api/v1/sessions/page-{i}/metadata",
            json={"tags": ["pagination-test"]},
        )

    # First page
    response = client.post(
        "/api/v1/sessions/search",
        json={"tags": ["pagination-test"], "limit": 2, "offset": 0},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 2
    assert data["limit"] == 2
    assert data["offset"] == 0

    # Second page
    response = client.post(
        "/api/v1/sessions/search",
        json={"tags": ["pagination-test"], "limit": 2, "offset": 2},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) == 2
    assert data["offset"] == 2

    # Cleanup
    for i in range(5):
        client.delete(f"/api/v1/sessions/page-{i}/metadata")


# ============================================================================
# Tags and Facets Tests
# ============================================================================


def test_get_all_tags(client):
    """Test getting all unique tags."""
    # Create sessions with various tags
    client.post("/api/v1/sessions/tags-1/metadata", json={"tags": ["python", "ml"]})
    client.post("/api/v1/sessions/tags-2/metadata", json={"tags": ["python", "web"]})

    response = client.get("/api/v1/sessions/tags")

    assert response.status_code == 200
    data = response.json()
    assert "python" in data["tags"]
    assert "ml" in data["tags"]
    assert "web" in data["tags"]

    # Cleanup
    client.delete("/api/v1/sessions/tags-1/metadata")
    client.delete("/api/v1/sessions/tags-2/metadata")


def test_get_facets(client):
    """Test getting search facets."""
    response = client.get("/api/v1/sessions/facets")

    assert response.status_code == 200
    data = response.json()
    assert "categories" in data
    assert "tags" in data
    assert "query_count_range" in data
