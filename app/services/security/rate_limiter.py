from __future__ import annotations

import threading
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta


def _utcnow() -> datetime:
    return datetime.now(UTC)


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

    def get_limit_info(self, key: str) -> dict[str, int]:
        """
        获取限流详细信息

        Returns:
            dict with keys:
            - attempts_used: 当前窗口内的尝试次数
            - attempts_remaining: 剩余可用次数
            - max_attempts: 最大允许次数
            - window_seconds: 时间窗口（秒）
            - retry_after: 如果被限流，多久后可重试（秒）
        """
        if not key:
            return {
                "attempts_used": 0,
                "attempts_remaining": self.max_attempts,
                "max_attempts": self.max_attempts,
                "window_seconds": int(self.window.total_seconds()),
                "retry_after": 0,
            }

        now = _utcnow()
        with self._lock:
            queue = self._events[key]
            self._trim(queue, now)
            used = len(queue)
            remaining = max(0, self.max_attempts - used)

            # 计算retry_after：如果被限流，需要等待最老的事件过期
            retry_after = 0
            if used >= self.max_attempts and queue:
                oldest = queue[0]
                expires_at = oldest + self.window
                retry_after = max(0, int((expires_at - now).total_seconds()))

            return {
                "attempts_used": used,
                "attempts_remaining": remaining,
                "max_attempts": self.max_attempts,
                "window_seconds": int(self.window.total_seconds()),
                "retry_after": retry_after,
            }

    def record(self, key: str) -> None:
        if not key:
            return
        now = _utcnow()
        with self._lock:
            queue = self._events[key]
            self._trim(queue, now)
            queue.append(now)

    def try_acquire(self, key: str) -> bool:
        """Atomically check and record an attempt. Returns True if allowed, False if rate limited."""
        if not key:
            return True
        now = _utcnow()
        with self._lock:
            queue = self._events[key]
            self._trim(queue, now)
            if len(queue) >= self.max_attempts:
                return False
            queue.append(now)
            return True

    def reset(self, key: str) -> None:
        if not key:
            return
        with self._lock:
            self._events.pop(key, None)

    def _trim(self, queue: deque[datetime], now: datetime) -> None:
        cutoff = now - self.window
        while queue and queue[0] < cutoff:
            queue.popleft()
