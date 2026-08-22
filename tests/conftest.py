"""Pytest configuration and shared fixtures for all tests."""

from unittest.mock import MagicMock
from pathlib import Path

import pytest


@pytest.fixture(scope="function", autouse=True)
def cleanup_test_users():
    """Clean up test users before and after each test."""
    import os
    import sqlite3

    db_path_value = os.environ.get("PYTEST_APP_DB_PATH", "").strip()
    if not db_path_value:
        yield
        return

    db_path = Path(db_path_value).resolve()
    canonical_db = Path("data/app.db").resolve()
    if db_path == canonical_db:
        raise RuntimeError("PYTEST_APP_DB_PATH must not point to the application database")

    # Clean up before test
    try:
        if db_path.exists():
            conn = sqlite3.connect(db_path)
            conn.execute("""
                DELETE FROM users
                WHERE username LIKE 'test_admin_%'
                   OR username LIKE 'test_user_%'
                   OR username = 'suspended_user'
                   OR username = 'testadmin'
            """)
            conn.commit()
            conn.close()
    except Exception:
        pass

    yield

    # Clean up after test
    try:
        if db_path.exists():
            conn = sqlite3.connect(db_path)
            conn.execute("""
                DELETE FROM users
                WHERE username LIKE 'test_admin_%'
                   OR username LIKE 'test_user_%'
                   OR username = 'suspended_user'
                   OR username = 'testadmin'
            """)
            conn.commit()
            conn.close()
    except Exception:
        pass


@pytest.fixture
def client():
    """
    Create FastAPI test client.

    Note: Due to httpx 0.28.1 and starlette 0.35.1 incompatibility,
    TestClient initialization fails. This fixture provides a mock client
    for isolation tests. For integration tests that need real HTTP client,
    consider using requests library or fixing the version conflict.
    """
    mock_client = MagicMock()

    # Setup default mock responses
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {}

    mock_client.get.return_value = mock_response
    mock_client.post.return_value = mock_response
    mock_client.put.return_value = mock_response
    mock_client.delete.return_value = mock_response

    return mock_client


@pytest.fixture
def auth_service():
    """Get auth service instance."""
    from app.api.dependencies import auth_service

    return auth_service


# ============================================================================
# Mock Authentication Fixtures for Security Tests
# ============================================================================


@pytest.fixture
def mock_auth_user():
    """Mock authenticated user with 'user' role."""
    return {
        "user_id": "test_user_123",
        "username": "test_user",
        "role": "user",
        "status": "active",
        "display_name": "Test User",
    }


@pytest.fixture
def mock_auth_admin():
    """Mock authenticated admin user."""
    return {
        "user_id": "test_admin_456",
        "username": "test_admin",
        "role": "admin",
        "status": "active",
        "display_name": "Test Admin",
    }


@pytest.fixture
def mock_auth_analyst():
    """Mock authenticated analyst user."""
    return {
        "user_id": "test_analyst_789",
        "username": "test_analyst",
        "role": "analyst",
        "status": "active",
        "display_name": "Test Analyst",
    }


@pytest.fixture
def mock_auth_viewer():
    """Mock authenticated viewer user."""
    return {
        "user_id": "test_viewer_101",
        "username": "test_viewer",
        "role": "viewer",
        "status": "active",
        "display_name": "Test Viewer",
    }


@pytest.fixture
def mock_auth_headers():
    """Mock authentication headers for API requests."""
    return {
        "Authorization": "Bearer mock_test_token_12345",
        "Content-Type": "application/json",
    }


@pytest.fixture
def mock_auth_service():
    """Mock AuthDBService for testing authentication flows."""
    mock_service = MagicMock()

    # Mock token validation
    mock_service.get_user_by_token.return_value = {
        "user_id": "test_user_123",
        "username": "test_user",
        "role": "user",
        "status": "active",
        "display_name": "Test User",
    }

    # Mock session management
    mock_service.touch_session.return_value = None
    mock_service.invalidate_token.return_value = True

    # Mock user creation
    mock_service.create_user.return_value = {
        "user_id": "new_user_123",
        "username": "new_user",
        "role": "viewer",
        "status": "active",
    }

    # Mock user retrieval
    mock_service.get_user_by_id.return_value = {
        "user_id": "test_user_123",
        "username": "test_user",
        "role": "user",
        "status": "active",
    }

    return mock_service


@pytest.fixture
def mock_user_with_documents():
    """Mock user with associated documents for isolation testing."""
    return {
        "user_id": "user_with_docs_123",
        "username": "user_with_docs",
        "role": "user",
        "status": "active",
        "display_name": "User With Documents",
        "allowed_sources": [
            "uploads/user_with_docs_123/document1.pdf",
            "uploads/user_with_docs_123/document2.pdf",
            "uploads/user_with_docs_123/notes.txt",
        ],
    }


@pytest.fixture
def mock_other_user():
    """Mock another user for testing isolation between users."""
    return {
        "user_id": "other_user_999",
        "username": "other_user",
        "role": "user",
        "status": "active",
        "display_name": "Other User",
    }
