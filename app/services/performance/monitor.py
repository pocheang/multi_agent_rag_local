"""Performance monitoring and metrics collection."""

import logging
import time
from collections import defaultdict
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MetricSnapshot:
    """Snapshot of metrics at a point in time."""

    timestamp: float
    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class LatencyStats:
    """Latency statistics."""

    count: int = 0
    total_time: float = 0.0
    min_time: float = float("inf")
    max_time: float = 0.0
    p50: float = 0.0
    p95: float = 0.0
    p99: float = 0.0
    samples: list[float] = field(default_factory=list)

    def record(self, duration: float) -> None:
        """Record a latency sample."""
        self.count += 1
        self.total_time += duration
        self.min_time = min(self.min_time, duration)
        self.max_time = max(self.max_time, duration)
        self.samples.append(duration)

        # Keep only recent samples for percentile calculation
        if len(self.samples) > 1000:
            self.samples = self.samples[-1000:]

        # Calculate percentiles
        if self.samples:
            sorted_samples = sorted(self.samples)
            self.p50 = sorted_samples[int(len(sorted_samples) * 0.50)]
            self.p95 = sorted_samples[int(len(sorted_samples) * 0.95)]
            self.p99 = sorted_samples[int(len(sorted_samples) * 0.99)]

    @property
    def avg_time(self) -> float:
        """Get average latency."""
        return self.total_time / self.count if self.count > 0 else 0.0


class PerformanceMonitor:
    """Performance monitoring and metrics collection."""

    def __init__(self):
        self._latencies: dict[str, LatencyStats] = defaultdict(LatencyStats)
        self._counters: dict[str, int] = defaultdict(int)
        self._gauges: dict[str, float] = defaultdict(float)
        self._start_time = time.time()

    @contextmanager
    def measure(self, operation: str, **labels):
        """Context manager to measure operation duration.

        Usage:
            with monitor.measure("query_execution"):
                # operation
                pass
        """
        start = time.time()
        try:
            yield
        finally:
            duration = time.time() - start
            self.record_latency(operation, duration, **labels)

    @asynccontextmanager
    async def measure_async(self, operation: str, **labels):
        """Async context manager to measure operation duration.

        Usage:
            async with monitor.measure_async("async_query"):
                # async operation
                await something()
        """
        start = time.time()
        try:
            yield
        finally:
            duration = time.time() - start
            self.record_latency(operation, duration, **labels)

    def record_latency(self, operation: str, duration: float, **labels) -> None:
        """Record operation latency."""
        key = self._make_key(operation, **labels)
        self._latencies[key].record(duration)

        # Log slow operations
        if duration > 5.0:  # 5 seconds threshold
            logger.warning(f"Slow operation detected: {operation} took {duration:.2f}s")

    def increment_counter(self, name: str, value: int = 1, **labels) -> None:
        """Increment a counter metric."""
        key = self._make_key(name, **labels)
        self._counters[key] += value

    def set_gauge(self, name: str, value: float, **labels) -> None:
        """Set a gauge metric."""
        key = self._make_key(name, **labels)
        self._gauges[key] = value

    def get_latency_stats(self, operation: str, **labels) -> LatencyStats:
        """Get latency statistics for an operation."""
        key = self._make_key(operation, **labels)
        return self._latencies.get(key, LatencyStats())

    def get_counter(self, name: str, **labels) -> int:
        """Get counter value."""
        key = self._make_key(name, **labels)
        return self._counters.get(key, 0)

    def get_gauge(self, name: str, **labels) -> float:
        """Get gauge value."""
        key = self._make_key(name, **labels)
        return self._gauges.get(key, 0.0)

    def get_all_stats(self) -> dict[str, Any]:
        """Get all performance statistics."""
        stats = {
            "uptime_seconds": time.time() - self._start_time,
            "latencies": {},
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
        }

        # Format latency stats
        for key, latency in self._latencies.items():
            stats["latencies"][key] = {
                "count": latency.count,
                "avg_ms": latency.avg_time * 1000,
                "min_ms": latency.min_time * 1000 if latency.min_time != float("inf") else 0,
                "max_ms": latency.max_time * 1000,
                "p50_ms": latency.p50 * 1000,
                "p95_ms": latency.p95 * 1000,
                "p99_ms": latency.p99 * 1000,
            }

        return stats

    def get_summary(self) -> str:
        """Get human-readable performance summary."""
        stats = self.get_all_stats()
        lines = [
            f"Performance Summary (uptime: {stats['uptime_seconds']:.0f}s)",
            "\n=== Latencies ===",
        ]

        for operation, metrics in stats["latencies"].items():
            lines.append(
                f"{operation}:"
                f" count={metrics['count']}"
                f" avg={metrics['avg_ms']:.1f}ms"
                f" p95={metrics['p95_ms']:.1f}ms"
                f" p99={metrics['p99_ms']:.1f}ms"
            )

        if stats["counters"]:
            lines.append("\n=== Counters ===")
            for name, value in stats["counters"].items():
                lines.append(f"{name}: {value}")

        if stats["gauges"]:
            lines.append("\n=== Gauges ===")
            for name, value in stats["gauges"].items():
                lines.append(f"{name}: {value:.2f}")

        return "\n".join(lines)

    def reset(self) -> None:
        """Reset all metrics."""
        self._latencies.clear()
        self._counters.clear()
        self._gauges.clear()
        self._start_time = time.time()

    def _make_key(self, name: str, **labels) -> str:
        """Make metric key with labels."""
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}{{{label_str}}}"


# Global monitor instance
_global_monitor: PerformanceMonitor | None = None


def get_monitor() -> PerformanceMonitor:
    """Get global performance monitor instance."""
    global _global_monitor
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    return _global_monitor
