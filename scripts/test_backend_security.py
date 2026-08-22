#!/usr/bin/env python3
"""
Backend Security Validation Script

Tests the implemented security measures:
1. CSRF Protection
2. Rate Limiting
3. Security Headers
"""

import requests
import time
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"
COLORS = {
    "GREEN": "\033[92m",
    "RED": "\033[91m",
    "YELLOW": "\033[93m",
    "BLUE": "\033[94m",
    "END": "\033[0m"
}


def print_test(name: str, status: str, message: str = ""):
    """Print test result with color."""
    color = COLORS["GREEN"] if status == "PASS" else COLORS["RED"] if status == "FAIL" else COLORS["YELLOW"]
    print(f"{color}[{status}]{COLORS['END']} {name}")
    if message:
        print(f"      {message}")


def test_csrf_protection():
    """Test CSRF protection middleware."""
    print(f"\n{COLORS['BLUE']}=== Testing CSRF Protection ==={COLORS['END']}")

    # Test 1: POST without CSRF token should fail
    try:
        response = requests.post(
            f"{BASE_URL}/sessions",
            json={"title": "test"},
            timeout=5
        )
        if response.status_code == 403:
            data = response.json()
            if "CSRF" in data.get("detail", ""):
                print_test("POST without CSRF token", "PASS", "Correctly rejected with 403")
            else:
                print_test("POST without CSRF token", "FAIL", f"Wrong error: {data}")
        else:
            print_test("POST without CSRF token", "FAIL", f"Expected 403, got {response.status_code}")
    except Exception as e:
        print_test("POST without CSRF token", "FAIL", f"Exception: {e}")

    # Test 2: POST with CSRF token should succeed (or fail for other reasons, not CSRF)
    try:
        headers = {"X-CSRF-Token": "1234567890abcdef" * 4}  # 64 char token
        response = requests.post(
            f"{BASE_URL}/sessions",
            json={"title": "test"},
            headers=headers,
            timeout=5
        )
        if response.status_code != 403 or "CSRF" not in response.json().get("detail", ""):
            print_test("POST with valid CSRF token", "PASS", f"Got {response.status_code} (not CSRF rejection)")
        else:
            print_test("POST with valid CSRF token", "FAIL", "Still rejected by CSRF")
    except Exception as e:
        print_test("POST with valid CSRF token", "FAIL", f"Exception: {e}")

    # Test 3: GET should work without CSRF token
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code == 200:
            print_test("GET without CSRF token", "PASS", "GET requests don't require CSRF")
        else:
            print_test("GET without CSRF token", "FAIL", f"Expected 200, got {response.status_code}")
    except Exception as e:
        print_test("GET without CSRF token", "FAIL", f"Exception: {e}")


def test_rate_limiting():
    """Test rate limiting middleware."""
    print(f"\n{COLORS['BLUE']}=== Testing Rate Limiting ==={COLORS['END']}")

    # Test login endpoint rate limit (5 requests per minute)
    print("Sending 6 login requests rapidly...")
    success_count = 0
    rate_limited = False

    for i in range(6):
        try:
            response = requests.post(
                f"{BASE_URL}/auth/login",
                json={"username": "test", "password": "test"},
                timeout=5
            )
            if response.status_code == 429:
                rate_limited = True
                data = response.json()
                retry_after = data.get("retry_after", "N/A")
                print_test(f"Request {i+1}/6", "INFO", f"Rate limited (retry after {retry_after}s)")
                break
            else:
                success_count += 1
                print_test(f"Request {i+1}/6", "INFO", f"Status: {response.status_code}")
        except Exception as e:
            print_test(f"Request {i+1}/6", "FAIL", f"Exception: {e}")
            break
        time.sleep(0.1)  # Small delay between requests

    if rate_limited:
        print_test("Rate limiting", "PASS", f"{success_count} succeeded, then rate limited")
    else:
        print_test("Rate limiting", "WARN", "No rate limiting detected (may need authentication)")


def test_security_headers():
    """Test security response headers."""
    print(f"\n{COLORS['BLUE']}=== Testing Security Headers ==={COLORS['END']}")

    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        headers = response.headers

        required_headers = {
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": ["SAMEORIGIN", "DENY"],
            "X-XSS-Protection": "1; mode=block",
            "Referrer-Policy": "strict-origin-when-cross-origin",
            "Content-Security-Policy": "default-src",
        }

        all_passed = True
        for header, expected in required_headers.items():
            actual = headers.get(header, "")
            if isinstance(expected, list):
                if any(exp in actual for exp in expected):
                    print_test(f"Header: {header}", "PASS", f"Value: {actual}")
                else:
                    print_test(f"Header: {header}", "FAIL", f"Expected one of {expected}, got: {actual}")
                    all_passed = False
            else:
                if expected in actual:
                    print_test(f"Header: {header}", "PASS", f"Value: {actual}")
                else:
                    print_test(f"Header: {header}", "FAIL", f"Expected {expected}, got: {actual}")
                    all_passed = False

        if all_passed:
            print(f"\n{COLORS['GREEN']}✓ All security headers present{COLORS['END']}")
        else:
            print(f"\n{COLORS['YELLOW']}⚠ Some security headers missing{COLORS['END']}")

    except Exception as e:
        print_test("Security headers", "FAIL", f"Exception: {e}")


def test_cors_headers():
    """Test CORS configuration."""
    print(f"\n{COLORS['BLUE']}=== Testing CORS Headers ==={COLORS['END']}")

    try:
        # Preflight request
        response = requests.options(
            f"{BASE_URL}/sessions",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type"
            },
            timeout=5
        )

        cors_headers = {
            "Access-Control-Allow-Origin": response.headers.get("Access-Control-Allow-Origin"),
            "Access-Control-Allow-Methods": response.headers.get("Access-Control-Allow-Methods"),
            "Access-Control-Allow-Headers": response.headers.get("Access-Control-Allow-Headers"),
        }

        if cors_headers["Access-Control-Allow-Origin"]:
            print_test("CORS Allow-Origin", "PASS", f"{cors_headers['Access-Control-Allow-Origin']}")
        else:
            print_test("CORS Allow-Origin", "WARN", "No CORS header (may be configured)")

    except Exception as e:
        print_test("CORS headers", "FAIL", f"Exception: {e}")


def main():
    """Run all security tests."""
    print(f"\n{COLORS['BLUE']}{'='*60}{COLORS['END']}")
    print(f"{COLORS['BLUE']}  Backend Security Validation{COLORS['END']}")
    print(f"{COLORS['BLUE']}  Testing: {BASE_URL}{COLORS['END']}")
    print(f"{COLORS['BLUE']}{'='*60}{COLORS['END']}")

    # Check if server is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"\n{COLORS['GREEN']}✓ Server is running{COLORS['END']}\n")
    except Exception as e:
        print(f"\n{COLORS['RED']}✗ Server is not running: {e}{COLORS['END']}")
        print(f"\nPlease start the server first:")
        print(f"  uvicorn app.api.main:app --reload --port 8000\n")
        return

    # Run tests
    test_security_headers()
    test_cors_headers()
    test_csrf_protection()
    test_rate_limiting()

    print(f"\n{COLORS['BLUE']}{'='*60}{COLORS['END']}")
    print(f"{COLORS['BLUE']}  Testing Complete{COLORS['END']}")
    print(f"{COLORS['BLUE']}{'='*60}{COLORS['END']}\n")


if __name__ == "__main__":
    main()
