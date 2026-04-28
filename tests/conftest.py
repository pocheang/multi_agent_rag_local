"""Pytest configuration and shared fixtures for all tests."""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="function", autouse=True)
def cleanup_test_users():
    """Clean up test users before and after each test."""
    import sqlite3
    import os

    db_path = "data/app.db"

    # Clean up before test
    try:
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            conn.execute("DELETE FROM users WHERE username LIKE 'test_admin_%' OR username LIKE 'test_user_%'")
            conn.commit()
            conn.close()
    except Exception:
        pass

    yield

    # Clean up after test
    try:
        if os.path.exists(db_path):
            conn = sqlite3.connect(db_path)
            conn.execute("DELETE FROM users WHERE username LIKE 'test_admin_%' OR username LIKE 'test_user_%'")
            conn.commit()
            conn.close()
    except Exception:
        pass


@pytest.fixture
def client():
    """Create FastAPI test client."""
    # Import here to avoid circular imports
    from app.api.main import app
    return TestClient(app)


@pytest.fixture
def auth_service():
    """Get auth service instance."""
    from app.api.dependencies import auth_service
    return auth_service
