"""What the distributed query guard does, pinned before it was split up.

`_acquire_redis` was one 110-line generator holding four jobs at once: a per-user
rate window, a distributed concurrency gate with a bounded queue, a fallback to
the in-memory guard for every way Redis can fail mid-acquire, and a release path
that repairs counters it could not decrement. It had no test.

The fallback is the part worth pinning hardest. Redis going away must never fail
a request -- it degrades to the in-memory guard -- and the counters already taken
must still come back, or the cluster leaks capacity until the keys expire.
"""

from __future__ import annotations

import pytest

from app.services.query import guard as guard_module
from app.services.query.guard import QueryLoadGuard, QueryOverloadedError, QueryRateLimitedError


class _FakeRedis:
    """Enough of a Redis client to drive the guard, with per-operation failures."""

    def __init__(
        self,
        *,
        fail: set[str] | None = None,
        start: dict[str, int] | None = None,
        reads: dict[str, int] | None = None,
    ) -> None:
        self.values: dict[str, int] = dict(start or {})
        self.fail = set(fail or ())
        # What GET reports regardless of what this client wrote -- the other
        # workers sharing these keys are the whole point of the redis backend.
        self.reads: dict[str, int] = dict(reads or {})
        self.calls: list[tuple[str, str]] = []

    def _maybe_fail(self, op: str, key: str) -> None:
        if f"{op}:{key}" in self.fail:
            raise OSError("connection reset by peer")

    def incr(self, key: str) -> int:
        self.calls.append(("incr", key))
        self._maybe_fail("incr", key)
        self.values[key] = int(self.values.get(key, 0)) + 1
        return self.values[key]

    def decr(self, key: str) -> int:
        self.calls.append(("decr", key))
        self._maybe_fail("decr", key)
        self.values[key] = int(self.values.get(key, 0)) - 1
        return self.values[key]

    def expire(self, key: str, seconds: int) -> None:
        self.calls.append(("expire", key))

    def get(self, key: str) -> int | None:
        self._maybe_fail("get", key)
        if key in self.reads:
            return self.reads[key]
        return self.values.get(key)

    def set(self, key: str, value: int, ex: int | None = None) -> None:
        self.calls.append(("set", key))
        self.values[key] = value


def _guard(**overrides) -> QueryLoadGuard:
    kwargs = {
        "per_user_max_requests": 10,
        "per_user_window_seconds": 60,
        "max_concurrent": 2,
        "max_waiting": 2,
        "acquire_timeout_ms": 50,
        "backend": "redis",
    }
    kwargs.update(overrides)
    return QueryLoadGuard(**kwargs)


@pytest.fixture
def redis(monkeypatch: pytest.MonkeyPatch) -> _FakeRedis:
    client = _FakeRedis()
    monkeypatch.setattr(guard_module, "_get_redis_client", lambda: client)
    return client


def _use(guard: QueryLoadGuard, user: str = "user-1") -> dict:
    with guard.acquire(user) as stats:
        return dict(stats)


def test_a_slot_is_taken_and_given_back(redis: _FakeRedis) -> None:
    stats = _use(_guard())

    assert stats["backend"] == "redis"
    assert redis.values["qguard:inflight"] == 0  # taken, then released on exit
    assert "qguard:waiting" not in redis.values  # never queued, so never counted


def test_the_slot_comes_back_even_when_the_body_raises(redis: _FakeRedis) -> None:
    guard = _guard()

    with pytest.raises(ValueError):
        with guard.acquire("user-1"):
            raise ValueError("boom")

    assert redis.values["qguard:inflight"] == 0


def test_a_user_over_the_window_is_rate_limited(redis: _FakeRedis) -> None:
    guard = _guard(per_user_max_requests=2)

    _use(guard)
    _use(guard)
    with pytest.raises(QueryRateLimitedError):
        _use(guard)

    # Rejected before any slot was taken.
    assert redis.values["qguard:inflight"] == 0


def test_a_full_gate_with_no_queue_is_refused(redis: _FakeRedis) -> None:
    redis.values["qguard:inflight"] = 5
    guard = _guard(max_concurrent=2, max_waiting=0)

    with pytest.raises(QueryOverloadedError, match="queue full"):
        _use(guard)

    assert redis.values["qguard:inflight"] == 5  # incremented to probe, then given back


def test_a_full_queue_is_refused_and_leaves_the_queue_count_where_it_found_it(redis: _FakeRedis) -> None:
    redis.values["qguard:inflight"] = 5
    redis.values["qguard:waiting"] = 2
    guard = _guard(max_concurrent=2, max_waiting=2)

    with pytest.raises(QueryOverloadedError, match="queue full"):
        _use(guard)

    assert redis.values["qguard:waiting"] == 2


def test_waiting_past_the_deadline_is_refused_and_the_queue_count_comes_back(redis: _FakeRedis) -> None:
    redis.values["qguard:inflight"] = 5
    guard = _guard(max_concurrent=2, max_waiting=2, acquire_timeout_ms=1)

    with pytest.raises(QueryOverloadedError, match="queue timeout"):
        _use(guard)

    assert redis.values["qguard:waiting"] == 0
    assert redis.values["qguard:inflight"] == 5


def test_redis_failing_the_rate_check_degrades_to_the_in_memory_guard(monkeypatch) -> None:
    """A dead Redis must cost the distributed counters, never the request."""

    client = _FakeRedis(fail={"incr:qguard:rate:user-1"})
    monkeypatch.setattr(guard_module, "_get_redis_client", lambda: client)

    stats = _use(_guard())

    assert stats["backend"] == "redis"  # what it tried
    assert ("incr", "qguard:inflight") not in client.calls  # never got that far


def test_redis_failing_the_gate_degrades_to_the_in_memory_guard(monkeypatch) -> None:
    client = _FakeRedis(fail={"incr:qguard:inflight"})
    monkeypatch.setattr(guard_module, "_get_redis_client", lambda: client)

    _use(_guard())  # yields rather than raising

    assert client.values.get("qguard:inflight") is None


def test_a_decrement_that_fails_repairs_a_counter_that_has_run_away(monkeypatch) -> None:
    """The release path is the last thing standing between a blip and a stuck cluster."""

    client = _FakeRedis(fail={"decr:qguard:inflight"}, reads={"qguard:inflight": 99})
    monkeypatch.setattr(guard_module, "_get_redis_client", lambda: client)

    _use(_guard(max_concurrent=2))

    # 99 is past 2 * max_concurrent, so the counter is reset rather than left stuck.
    assert client.values["qguard:inflight"] == 0
    assert ("set", "qguard:inflight") in client.calls


def test_a_decrement_that_fails_leaves_a_plausible_counter_alone(monkeypatch) -> None:
    client = _FakeRedis(fail={"decr:qguard:inflight"}, reads={"qguard:inflight": 1})
    monkeypatch.setattr(guard_module, "_get_redis_client", lambda: client)

    _use(_guard(max_concurrent=2))

    assert ("set", "qguard:inflight") not in client.calls


def test_no_client_at_all_uses_the_in_memory_guard(monkeypatch) -> None:
    monkeypatch.setattr(guard_module, "_get_redis_client", lambda: None)

    stats = _use(_guard())

    assert stats["backend"] == "memory"
