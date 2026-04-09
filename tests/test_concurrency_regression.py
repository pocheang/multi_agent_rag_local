from __future__ import annotations

import threading
import time
import importlib

import pytest

from app.services.background_queue import BackgroundTaskQueue
from app.services.query_guard import QueryLoadGuard, QueryOverloadedError
from app.services.query_result_cache import QueryResultCache


class _FakeRedis:
    def __init__(self):
        self._lock = threading.Lock()
        self._data: dict[str, int | str] = {}

    def ping(self):
        return True

    def incr(self, key: str) -> int:
        with self._lock:
            cur = int(self._data.get(key, 0) or 0) + 1
            self._data[key] = cur
            return cur

    def decr(self, key: str) -> int:
        with self._lock:
            cur = int(self._data.get(key, 0) or 0) - 1
            self._data[key] = cur
            return cur

    def expire(self, key: str, seconds: int):
        return True

    def set(self, key: str, value: str, nx: bool = False, ex: int | None = None):
        with self._lock:
            if nx and key in self._data:
                return False
            self._data[key] = value
            return True

    def get(self, key: str):
        with self._lock:
            return self._data.get(key)

    def exists(self, key: str) -> int:
        with self._lock:
            return 1 if key in self._data else 0

    def delete(self, key: str) -> int:
        with self._lock:
            existed = key in self._data
            self._data.pop(key, None)
            return 1 if existed else 0

    def setex(self, key: str, ttl: int, value: str):
        with self._lock:
            self._data[key] = value
            return True


def test_background_queue_stop_with_drain_runs_enqueued_tasks():
    q = BackgroundTaskQueue(maxsize=32, workers=2, name="test-q")
    counter = {"n": 0}
    lock = threading.Lock()

    def _task():
        time.sleep(0.02)
        with lock:
            counter["n"] += 1

    q.start()
    for _ in range(10):
        assert q.submit(_task) is True
    q.stop(timeout=2.0, drain=True)

    assert counter["n"] == 10
    assert q.stats()["workers"] == 0


def test_query_result_cache_distributed_inflight_lock(monkeypatch: pytest.MonkeyPatch):
    fake = _FakeRedis()
    monkeypatch.setattr("app.services.query_result_cache._get_redis_client", lambda: fake)

    c1 = QueryResultCache(backend="redis", ttl_seconds=20, max_items=100, session_ttl_seconds=20)
    c2 = QueryResultCache(backend="redis", ttl_seconds=20, max_items=100, session_ttl_seconds=20)
    key = "k1"

    assert c1.mark_inflight(key) is True
    assert c2.mark_inflight(key) is False
    c1.clear_inflight(key)
    assert c2.mark_inflight(key) is True


def test_query_guard_redis_waiting_limit(monkeypatch: pytest.MonkeyPatch):
    fake = _FakeRedis()
    monkeypatch.setattr("app.services.query_guard._get_redis_client", lambda: fake)

    guard = QueryLoadGuard(
        per_user_max_requests=100,
        per_user_window_seconds=60,
        max_concurrent=1,
        max_waiting=1,
        acquire_timeout_ms=120,
        backend="redis",
    )
    hold = threading.Event()

    def _holder():
        with guard.acquire("u1"):
            hold.wait(timeout=1.0)

    t = threading.Thread(target=_holder, daemon=True)
    t.start()
    time.sleep(0.05)

    second_entered = threading.Event()
    second_error: list[Exception] = []

    def _second():
        try:
            with guard.acquire("u2"):
                second_entered.set()
        except Exception as e:  # noqa: BLE001 - test captures expected runtime errors
            second_error.append(e)

    t2 = threading.Thread(target=_second, daemon=True)
    t2.start()
    time.sleep(0.03)

    with pytest.raises(QueryOverloadedError, match="query queue full"):
        with guard.acquire("u3"):
            pass

    hold.set()
    t.join(timeout=1.0)
    t2.join(timeout=1.0)

    # second should not be "queue full" because it is the single waiter slot
    if second_error:
        assert isinstance(second_error[0], QueryOverloadedError)
        assert "timeout" in str(second_error[0]).lower()
    else:
        assert second_entered.is_set()


def test_vector_store_lock_serializes_operations(monkeypatch: pytest.MonkeyPatch):
    if importlib.util.find_spec("langchain_core") is None:
        pytest.skip("langchain_core not installed in current test environment")
    from app.retrievers import vector_store as vs

    class _FakeStore:
        def __init__(self):
            self.active = 0
            self.max_active = 0
            self.lock = threading.Lock()

        def _enter(self):
            with self.lock:
                self.active += 1
                self.max_active = max(self.max_active, self.active)

        def _exit(self):
            with self.lock:
                self.active -= 1

        def add_documents(self, *args, **kwargs):
            self._enter()
            try:
                time.sleep(0.06)
            finally:
                self._exit()

        def similarity_search_with_relevance_scores(self, *args, **kwargs):
            self._enter()
            try:
                time.sleep(0.06)
                return []
            finally:
                self._exit()

    store = _FakeStore()
    monkeypatch.setattr(vs, "get_vector_store", lambda: store)

    t1 = threading.Thread(target=lambda: vs.add_documents([{"x": 1}]), daemon=True)
    t2 = threading.Thread(target=lambda: vs.similarity_search("hello"), daemon=True)
    t1.start()
    t2.start()
    t1.join(timeout=1.0)
    t2.join(timeout=1.0)

    assert store.max_active == 1
