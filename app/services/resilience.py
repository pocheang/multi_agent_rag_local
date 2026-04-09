import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Callable

from app.core.config import get_settings


class CircuitBreakerOpenError(RuntimeError):
    pass


@dataclass
class _BreakerState:
    fails: int = 0
    opened_until: float = 0.0


_BREAKERS: dict[str, _BreakerState] = {}


def call_with_circuit_breaker(name: str, fn: Callable[[], Any]) -> Any:
    settings = get_settings()
    if not bool(getattr(settings, "circuit_breaker_enabled", True)):
        return fn()
    now = time.time()
    state = _BREAKERS.setdefault(name, _BreakerState())
    if state.opened_until > now:
        raise CircuitBreakerOpenError(f"circuit_open:{name}")
    try:
        result = fn()
        state.fails = 0
        state.opened_until = 0.0
        return result
    except Exception:
        state.fails += 1
        threshold = int(getattr(settings, "circuit_breaker_fail_threshold", 3) or 3)
        cooldown = int(getattr(settings, "circuit_breaker_cooldown_seconds", 30) or 30)
        if state.fails >= threshold:
            state.opened_until = now + max(1, cooldown)
            state.fails = 0
        raise


class TTLCache:
    def __init__(self, ttl_seconds: int, max_items: int):
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.max_items = max(1, int(max_items))
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()

    def _evict(self) -> None:
        now = time.time()
        stale_keys = [k for k, (exp, _v) in self._store.items() if exp <= now]
        for k in stale_keys:
            self._store.pop(k, None)
        while len(self._store) > self.max_items:
            self._store.popitem(last=False)

    def get(self, key: str) -> Any | None:
        self._evict()
        item = self._store.get(key)
        if not item:
            return None
        exp, value = item
        if exp <= time.time():
            self._store.pop(key, None)
            return None
        self._store.move_to_end(key, last=True)
        return value

    def set(self, key: str, value: Any) -> None:
        self._evict()
        self._store[key] = (time.time() + self.ttl_seconds, value)
        self._store.move_to_end(key, last=True)
        self._evict()
