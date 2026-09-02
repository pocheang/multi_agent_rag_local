"""CSRF is enforced in one place, and that place fails closed.

Until 2026-09-02 the repository carried two things named CSRF and only one of
them worked. `CSRFProtectionMiddleware` required a `session_id` cookie that no
route ever set, so its first branch returned on every request; the browser
meanwhile minted its own token in `lib/csrf.ts` and sent it in a header no
server component had stored. Both were deleted.

What remains is `_enforce_cookie_csrf`, reached from `_resolve_authenticated_user`
and therefore from every one of `_require_user`, `_require_user_and_token`,
`_require_permission` and `require_admin`. Its shape is the reason the other two
were removable rather than merely broken:

- it applies only when the request authenticated **by cookie**, because a
  cross-site page cannot set an `Authorization` header, so bearer traffic is not
  CSRF-vulnerable and does not need a token to prove it;
- it requires an allow-listed `Origin` (or `Referer`) on unsafe methods, and a
  **missing** one is a refusal, not a pass.

That last property is the whole defence: an attacker's page can omit headers far
more easily than it can forge one. These tests exist so a later reader who finds
a CSRF check with no token anywhere cannot conclude this one is theatre too.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException, Request

from app.api.utils.auth_helpers import _enforce_cookie_csrf

ALLOWED_ORIGIN = "http://localhost:5173"


def _request(method: str = "POST", headers: dict[str, str] | None = None) -> Request:
    raw = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    return Request(
        {
            "type": "http",
            "method": method,
            "path": "/api/v1/documents",
            "headers": raw,
            "scheme": "http",
            "server": ("testserver", 80),
            "query_string": b"",
        }
    )


def _refused(request: Request, token_source: str) -> bool:
    try:
        _enforce_cookie_csrf(request, token_source)
    except HTTPException as exc:
        assert exc.status_code == 403
        return True
    return False


class TestCookieAuthIsChecked:
    def test_a_missing_origin_is_refused(self) -> None:
        """The property the whole defence rests on: absent is not permitted."""

        assert _refused(_request(), "cookie")

    def test_a_foreign_origin_is_refused(self) -> None:
        assert _refused(_request(headers={"origin": "https://attacker.example"}), "cookie")

    def test_an_empty_origin_header_is_refused(self) -> None:
        """A header present but blank must not read as 'allow-listed'."""

        assert _refused(_request(headers={"origin": "   "}), "cookie")

    def test_an_allowed_origin_passes(self) -> None:
        assert not _refused(_request(headers={"origin": ALLOWED_ORIGIN}), "cookie")

    def test_a_referer_stands_in_for_a_missing_origin(self) -> None:
        assert not _refused(_request(headers={"referer": f"{ALLOWED_ORIGIN}/chat"}), "cookie")

    @pytest.mark.parametrize("method", ["POST", "PUT", "PATCH", "DELETE"])
    def test_every_unsafe_method_is_covered(self, method: str) -> None:
        assert _refused(_request(method=method), "cookie")

    @pytest.mark.parametrize("method", ["GET", "HEAD", "OPTIONS"])
    def test_safe_methods_are_not(self, method: str) -> None:
        assert not _refused(_request(method=method), "cookie")


class TestBearerAuthIsExempt:
    """Not an oversight, and not a hole: a cross-site request cannot carry an
    Authorization header, so there is nothing here for a token to defend."""

    def test_bearer_without_an_origin_passes(self) -> None:
        assert not _refused(_request(), "bearer")

    def test_an_unauthenticated_request_is_not_this_check_s_business(self) -> None:
        assert not _refused(_request(), None)
