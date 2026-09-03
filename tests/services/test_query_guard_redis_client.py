"""The shared Redis client is opened once, and a failure stops the retrying.

Every request asks for this client, so a Redis that is down must cost one
connection attempt per cooldown rather than one per query -- at 0.2s of connect
timeout, retrying per request turns an unavailable dependency into an outage.
"""

from __future__ import annotations

import sys
import types

import pytest

from app.services.query import guard as guard_module


class _FakeClient:
    def __init__(self, *, ping_error: Exception | None = None) -> None:
        self.ping_error = ping_error
        self.closed = False

    def ping(self) -> bool:
        if self.ping_error is not None:
            raise self.ping_error
        return True

    def close(self) -> None:
        self.closed = True


@pytest.fixture(autouse=True)
def _fresh_module_state(monkeypatch: pytest.MonkeyPatch) -> None:
    """The client and its cooldown are module globals; every test starts from none."""

    monkeypatch.setattr(guard_module, "_REDIS_CLIENT", None)
    monkeypatch.setattr(guard_module, "_REDIS_UNAVAILABLE_UNTIL", 0.0)


def _install_redis(monkeypatch: pytest.MonkeyPatch, client: _FakeClient | None, *, error: Exception | None = None):
    """Stand a fake `redis` module in front of the import inside _connect_redis."""

    calls: list[int] = []

    def from_url(url: str, **kwargs):
        calls.append(1)
        if error is not None:
            raise error
        return client

    monkeypatch.setitem(sys.modules, "redis", types.SimpleNamespace(from_url=from_url))
    return calls


def test_the_client_is_opened_once_and_reused(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient()
    calls = _install_redis(monkeypatch, client)

    assert guard_module._get_redis_client() is client
    assert guard_module._get_redis_client() is client
    assert len(calls) == 1


def test_a_connection_failure_starts_a_cooldown_instead_of_retrying(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_redis(monkeypatch, None, error=OSError("connection refused"))

    assert guard_module._get_redis_client() is None
    assert guard_module._get_redis_client() is None
    assert len(calls) == 1  # the second call is inside the cooldown


def test_a_client_that_will_not_answer_ping_is_closed_rather_than_kept(monkeypatch: pytest.MonkeyPatch) -> None:
    """from_url can succeed while the connection never worked, leaving a client to clean up."""

    client = _FakeClient(ping_error=OSError("no route to host"))
    _install_redis(monkeypatch, client)

    assert guard_module._get_redis_client() is None
    assert client.closed


def test_redis_not_installed_is_routine_and_also_cools_down(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = _install_redis(monkeypatch, None, error=ImportError("no module named redis"))

    assert guard_module._get_redis_client() is None
    assert guard_module._get_redis_client() is None
    assert len(calls) == 1


def test_the_cooldown_expires_and_the_next_call_tries_again(monkeypatch: pytest.MonkeyPatch) -> None:
    client = _FakeClient()
    calls = _install_redis(monkeypatch, client)
    monkeypatch.setattr(guard_module, "_REDIS_UNAVAILABLE_UNTIL", 1.0)
    monkeypatch.setattr(guard_module.time, "monotonic", lambda: 0.5)

    assert guard_module._get_redis_client() is None  # still cooling
    assert calls == []

    monkeypatch.setattr(guard_module.time, "monotonic", lambda: 2.0)
    assert guard_module._get_redis_client() is client
    assert len(calls) == 1
