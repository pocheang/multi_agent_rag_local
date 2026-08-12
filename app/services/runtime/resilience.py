import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings


class CircuitBreakerOpenError(RuntimeError):
    pass


@dataclass
class _BreakerState:
    fails: int = 0
    opened_until: float = 0.0


_BREAKERS: dict[str, _BreakerState] = {}
_BREAKERS_LOCK = threading.Lock()


def record_circuit_failure(name: str) -> dict[str, Any]:
    """Record a failure in the sole process-wide breaker registry."""
    settings = get_settings()
    now = time.time()
    with _BREAKERS_LOCK:
        state = _BREAKERS.setdefault(name, _BreakerState())
        state.fails += 1
        threshold = int(getattr(settings, "circuit_breaker_fail_threshold", 5) or 5)
        cooldown = int(getattr(settings, "circuit_breaker_cooldown_seconds", 60) or 60)
        if state.fails >= threshold:
            state.opened_until = now + max(1, cooldown)
            state.fails = 0
        return circuit_breaker_snapshot(name, now=now)


def record_circuit_success(name: str) -> dict[str, Any]:
    """Reset a successful component in the sole process-wide registry."""
    with _BREAKERS_LOCK:
        state = _BREAKERS.setdefault(name, _BreakerState())
        state.fails = 0
        state.opened_until = 0.0
        return circuit_breaker_snapshot(name)


def circuit_breaker_snapshot(name: str, *, now: float | None = None) -> dict[str, Any]:
    """Return safe monitoring data for the single runtime breaker registry."""
    current = time.time() if now is None else now
    state = _BREAKERS.setdefault(name, _BreakerState())
    is_open = state.opened_until > current
    return {
        "name": name,
        "state": "OPEN" if is_open else "CLOSED",
        "failure_count": state.fails,
        "opened_until": state.opened_until,
        "success_count": 0,
        "success_rate": 0.0,
        "last_failure_time": None,
        "time_in_current_state": max(0.0, state.opened_until - current) if is_open else 0.0,
    }


def reset_circuit_breakers() -> None:
    """Clear every runtime breaker during application-controlled cleanup."""
    with _BREAKERS_LOCK:
        _BREAKERS.clear()


def call_with_circuit_breaker(name: str, fn: Callable[[], Any]) -> Any:
    settings = get_settings()
    if not bool(getattr(settings, "circuit_breaker_enabled", True)):
        return fn()
    now = time.time()

    # HIGH PRIORITY FIX: Keep lock held during check to prevent race condition
    with _BREAKERS_LOCK:
        state = _BREAKERS.setdefault(name, _BreakerState())
        is_open = state.opened_until > now

        # Check circuit state while holding lock to prevent race condition
        if is_open:
            raise CircuitBreakerOpenError(f"circuit_open:{name}")

    try:
        result = fn()
        # Success: reset failure count
        with _BREAKERS_LOCK:
            state = _BREAKERS.get(name)
            if state:
                state.fails = 0
                state.opened_until = 0.0
        return result
    except Exception:
        # Failure: increment counter and potentially open circuit
        with _BREAKERS_LOCK:
            state = _BREAKERS.get(name)
            if state:
                state.fails += 1
                threshold = int(getattr(settings, "circuit_breaker_fail_threshold", 5) or 5)
                cooldown = int(getattr(settings, "circuit_breaker_cooldown_seconds", 60) or 60)
                if state.fails >= threshold:
                    state.opened_until = time.time() + max(1, cooldown)
                    # Reset fails to avoid overflow on repeated failures
                    state.fails = 0
        raise


class TTLCache:
    def __init__(self, ttl_seconds: int, max_items: int):
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.max_items = max(1, int(max_items))
        self._store: OrderedDict[str, tuple[float, Any]] = OrderedDict()
        self._lock = threading.RLock()
        self._last_eviction = time.time()
        self._eviction_interval = max(1.0, float(ttl_seconds) / 10.0)  # Evict at most every 10% of TTL

    def _should_evict(self) -> bool:
        """Check if enough time has passed since last eviction to warrant another one."""
        return (time.time() - self._last_eviction) >= self._eviction_interval

    def _evict(self) -> None:
        """Evict expired items and enforce max_items limit."""
        now = time.time()
        self._last_eviction = now

        # Lazy eviction: only scan and remove expired items
        stale_keys = [k for k, (exp, _v) in self._store.items() if exp <= now]
        for k in stale_keys:
            self._store.pop(k, None)

        # Enforce max_items limit
        while len(self._store) > self.max_items:
            self._store.popitem(last=False)

    def get(self, key: str) -> Any | None:
        with self._lock:
            item = self._store.get(key)
            if not item:
                # Opportunistic eviction: only if interval has passed
                if self._should_evict():
                    self._evict()
                return None

            exp, value = item
            now = time.time()

            # Check if this specific item is expired
            if exp <= now:
                self._store.pop(key, None)
                # Opportunistic eviction: only if interval has passed
                if self._should_evict():
                    self._evict()
                return None

            # Move to end for LRU
            self._store.move_to_end(key, last=True)

            # Opportunistic eviction: only if interval has passed
            if self._should_evict():
                self._evict()

            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            # Set the new value
            self._store[key] = (time.time() + self.ttl_seconds, value)
            self._store.move_to_end(key, last=True)

            # Only evict if we've exceeded max_items or interval has passed
            if len(self._store) > self.max_items or self._should_evict():
                self._evict()

