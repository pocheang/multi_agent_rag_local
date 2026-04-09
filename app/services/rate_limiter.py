from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
import threading


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SlidingWindowLimiter:
    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max(1, int(max_attempts))
        self.window = timedelta(seconds=max(1, int(window_seconds)))
        self._events: dict[str, deque[datetime]] = defaultdict(deque)
        self._lock = threading.Lock()

    def is_limited(self, key: str) -> bool:
        if not key:
            return False
        now = _utcnow()
        with self._lock:
            queue = self._events[key]
            self._trim(queue, now)
            if len(queue) >= self.max_attempts:
                return True
            return False

    def record(self, key: str) -> None:
        if not key:
            return
        now = _utcnow()
        with self._lock:
            queue = self._events[key]
            self._trim(queue, now)
            queue.append(now)

    def reset(self, key: str) -> None:
        if not key:
            return
        with self._lock:
            self._events.pop(key, None)

    def _trim(self, queue: deque[datetime], now: datetime) -> None:
        cutoff = now - self.window
        while queue and queue[0] < cutoff:
            queue.popleft()
