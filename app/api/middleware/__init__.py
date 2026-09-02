"""
Security middleware for the QueryMind API.

Rate limiting on sensitive endpoints. CSRF lived here too until 2026-09-02:
its middleware required a `session_id` cookie that nothing in the application
ever set, so it returned early on every request, and the token the browser
sent was one no server component had minted or stored. CSRF is enforced by
`_enforce_cookie_csrf` in app/api/utils/auth_helpers.py, on the only auth mode
that is vulnerable to it.
"""
