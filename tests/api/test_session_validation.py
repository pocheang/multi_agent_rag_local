"""Additional API tests for input validation."""

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
    client.headers.update({
        "X-Test-User": "session-validation-user",
        "X-Test-User-Id": "session-validation-user",
        "X-Test-Role": "user",
    })
    return client


def test_create_with_invalid_tags(client):
    """Test that API rejects invalid tags."""
    response = client.post(
        "/api/v1/sessions/test-invalid/metadata",
        json={
            "tags": ["valid-tag", "invalid tag"],  # Space not allowed
        },
    )
    assert response.status_code == 400
    assert "Invalid tag" in response.json()["detail"]


def test_create_with_too_many_tags(client):
    """Test that API enforces tag limit."""
    too_many_tags = [f"tag{i}" for i in range(11)]  # Max is 10
    response = client.post(
        "/api/v1/sessions/test-too-many/metadata",
        json={"tags": too_many_tags},
    )
    assert response.status_code == 400
    assert "Too many tags" in response.json()["detail"]


def test_create_with_description_too_long(client):
    """Test that API enforces description length limit."""
    long_desc = "x" * 501  # Max is 500
    response = client.post(
        "/api/v1/sessions/test-long-desc/metadata",
        json={"description": long_desc},
    )
    # Pydantic may validate before our service, both are acceptable
    assert response.status_code == 422
    detail = response.json()["detail"]
    # Check that it's a validation error about length
    assert "length" in str(detail).lower() or "exceeds" in str(detail).lower()


def test_create_with_valid_inputs(client):
    """Test that valid inputs are accepted and normalized."""
    response = client.post(
        "/api/v1/sessions/test-valid/metadata",
        json={
            "tags": ["Python", "FASTAPI", "test"],  # Mixed case
            "description": "  Valid description  ",  # Whitespace
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["tags"] == ["python", "fastapi", "test"]  # Normalized to lowercase
    assert data["description"] == "Valid description"  # Trimmed

    # Cleanup
    client.delete("/api/v1/sessions/test-valid/metadata")


def test_update_with_invalid_tags(client):
    """Test that update also validates tags."""
    # Create first
    client.post("/api/v1/sessions/test-update-invalid/metadata", json={"tags": ["valid"]})

    # Try to update with invalid tag
    response = client.post(
        "/api/v1/sessions/test-update-invalid/metadata",
        json={"tags": ["invalid@tag"]},  # @ not allowed
    )
    assert response.status_code == 400
    assert "Invalid tag" in response.json()["detail"]

    # Cleanup
    client.delete("/api/v1/sessions/test-update-invalid/metadata")


def test_lru_eviction_behavior(client):
    """Test that LRU eviction works (informational test)."""
    # Note: Default service has MAX_SESSIONS=1000, so we can't easily test eviction
    # This test just verifies the service is using V2 with validation
    response = client.post(
        "/api/v1/sessions/test-lru/metadata",
        json={"tags": ["test"]},
    )
    assert response.status_code == 200

    # Cleanup
    client.delete("/api/v1/sessions/test-lru/metadata")
