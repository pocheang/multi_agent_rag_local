"""The rate limits have to reach the routes they name.

Eight admin endpoints carried `@limiter.limit(...)` and none of them was limited.
The decorator came from a slowapi wrapper, slowapi was never a dependency -- not
in pyproject, not in the locks, not installed -- so the import guard fell through
to a no-op decorator every time. Creating an administrator, resetting a password
and resetting an approval token were unlimited, and the code said otherwise on
the line above each one.

The limits are rules in the middleware now, which is registered on the app, and
the failure mode moves with them: a rule whose pattern no longer matches any
route is silently no protection at all. So the first test asks the OpenAPI
document rather than trusting the patterns, and the second names the eight
operations explicitly, because "every rule matches something" would still pass if
a rule were deleted.
"""

from __future__ import annotations

import pytest
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient

from app.api.middleware.rate_limit import RATE_LIMIT_RULES, RateLimitMiddleware

# The operations that used to carry a decorator, as (method, concrete path).
PREVIOUSLY_DECORATED = [
    ("GET", "/admin/users", "list_users"),
    ("POST", "/admin/users/u-1/credits/add", "credit_add"),
    ("PATCH", "/admin/users/u-1/role", "role_update"),
    ("POST", "/admin/users/create-admin", "admin_create"),
    ("POST", "/admin/users/u-1/reset-approval-token", "approval_token_reset"),
    ("POST", "/admin/users/u-1/reset-password", "admin_password_reset"),
    ("PATCH", "/admin/users/u-1/status", "status_update"),
    ("GET", "/admin/audit-logs", "audit_logs"),
]


def _routes() -> set[tuple[str, str]]:
    import app.api.main as main

    return {
        (method.upper(), path)
        for path, operations in main.app.openapi()["paths"].items()
        for method in operations
        if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}
    }


class TestEveryRuleGuardsSomethingThatExists:
    def test_no_rule_points_at_a_route_that_is_gone(self) -> None:
        """A renamed route turns its limit off without a word."""

        routes = _routes()
        orphaned = []
        for rule in RATE_LIMIT_RULES:
            concrete = [
                (method, path.replace("{user_id}", "u-1").replace("{filename}", "f"))
                for method, path in routes
                if method in rule.methods
            ]
            if not any(rule.matches(method, path) for method, path in concrete):
                orphaned.append(rule.name)

        assert not orphaned, f"these rules match no route: {orphaned}"

    @pytest.mark.parametrize(("method", "path", "expected"), PREVIOUSLY_DECORATED)
    def test_each_operation_that_lost_its_decorator_is_covered(self, method: str, path: str, expected: str) -> None:
        matched = [rule.name for rule in RATE_LIMIT_RULES if rule.matches(method, path)]

        assert matched == [expected], f"{method} {path} matched {matched}"

    def test_a_user_id_does_not_get_its_own_bucket(self) -> None:
        """Keying on the path would make the limit per target rather than per
        operation -- five password resets *each* rather than five in total."""

        one = next(r for r in RATE_LIMIT_RULES if r.matches("POST", "/admin/users/aaa/reset-password"))
        another = next(r for r in RATE_LIMIT_RULES if r.matches("POST", "/admin/users/bbb/reset-password"))

        assert one.name == another.name


class TestTheLimitIsEnforced:
    """Driven through a minimal app so the counters cannot be shared with another
    test, and so this asserts the middleware rather than the route stack."""

    @staticmethod
    def _client() -> TestClient:
        app = Starlette(routes=[Route("/auth/login", lambda request: PlainTextResponse("ok"), methods=["POST"])])
        app.add_middleware(RateLimitMiddleware)
        return TestClient(app)

    def test_requests_beyond_the_limit_are_refused(self) -> None:
        client = self._client()
        login = next(r for r in RATE_LIMIT_RULES if r.name == "login")

        allowed = [client.post("/auth/login").status_code for _ in range(login.max_requests)]
        refused = client.post("/auth/login")

        assert allowed == [200] * login.max_requests
        assert refused.status_code == 429
        assert refused.json()["error_code"] == "RATE_LIMIT_EXCEEDED"
        assert refused.headers.get("Retry-After")

    def test_a_path_with_no_rule_is_untouched(self) -> None:
        app = Starlette(routes=[Route("/health", lambda request: PlainTextResponse("ok"))])
        app.add_middleware(RateLimitMiddleware)
        client = TestClient(app)

        assert [client.get("/health").status_code for _ in range(20)] == [200] * 20
