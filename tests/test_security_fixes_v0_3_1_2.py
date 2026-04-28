"""
Security fixes verification for v0.3.1.2
Tests password policy, cookie security, and login error messages.
"""
import pytest


def test_password_policy_min_length():
    """Test password minimum length increased to 12 characters."""
    from app.services.auth.validation import validate_password

    # Should reject 8 character passwords
    with pytest.raises(ValueError, match="at least 12 characters"):
        validate_password("Pass123!")

    # Should reject 11 character passwords
    with pytest.raises(ValueError, match="at least 12 characters"):
        validate_password("Pass123456!")


def test_password_policy_max_length():
    """Test password maximum length of 128 characters (DoS protection)."""
    from app.services.auth.validation import validate_password

    # Should reject passwords over 128 characters
    long_password = "P@ssw0rd" + "x" * 130
    with pytest.raises(ValueError, match="must not exceed 128 characters"):
        validate_password(long_password)


def test_password_policy_special_chars():
    """Test password requires special characters."""
    from app.services.auth.validation import validate_password

    # Should reject passwords without special characters
    with pytest.raises(ValueError, match="must include special characters"):
        validate_password("Password1234")

    with pytest.raises(ValueError, match="must include special characters"):
        validate_password("Abcdefghijkl1234")


def test_password_policy_valid():
    """Test valid password passes all checks."""
    from app.services.auth.validation import validate_password

    # Should accept valid 12+ char password with special chars
    result = validate_password("P@ssw0rd1234")
    assert result == "P@ssw0rd1234"

    result = validate_password("MySecure!Pass123")
    assert result == "MySecure!Pass123"


def test_cookie_security_defaults():
    """Test cookie security defaults are hardened in code."""
    from app.core.config import Settings
    from pydantic import Field

    # Check the Field default values (not runtime .env overrides)
    secure_field = Settings.model_fields['auth_cookie_secure']
    samesite_field = Settings.model_fields['auth_cookie_samesite']

    # Should default to secure=true (HTTPS-only)
    assert secure_field.default is True, "auth_cookie_secure should default to True"

    # Should default to samesite=strict (CSRF protection)
    assert samesite_field.default == "strict", "auth_cookie_samesite should default to 'strict'"


def test_login_error_message_unified():
    """Test login errors don't leak user existence information."""
    pytest.importorskip("fastapi")
    from fastapi.testclient import TestClient

    api_main = pytest.importorskip("app.api.main")

    client = TestClient(api_main.app)

    # Test with non-existent user
    res1 = client.post("/auth/login", json={
        "username": "nonexistent_user_12345",
        "password": "WrongPassword123!"
    })

    # Test with existing user but wrong password (if default admin exists)
    res2 = client.post("/auth/login", json={
        "username": "admin",
        "password": "WrongPassword123!"
    })

    # Both should return same generic error message
    assert res1.status_code == 401
    assert res2.status_code == 401

    # Should not reveal whether user exists
    assert res1.json()["detail"] == "invalid credentials"
    assert res2.json()["detail"] == "invalid credentials"

    # Should NOT contain "user not found" or "invalid password"
    assert "user not found" not in res1.json()["detail"].lower()
    assert "invalid password" not in res1.json()["detail"].lower()
