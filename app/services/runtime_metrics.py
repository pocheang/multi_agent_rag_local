from __future__ import annotations

import threading
import time
from typing import Any


class RuntimeMetrics:
    def __init__(self):
        self._lock = threading.Lock()
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._hist: dict[str, list[float]] = {}

    def inc(self, name: str, value: float = 1.0) -> None:
        with self._lock:
            self._counters[name] = float(self._counters.get(name, 0.0) + value)

    def set_gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = float(value)

    def observe(self, name: str, value: float) -> None:
        with self._lock:
            arr = self._hist.setdefault(name, [])
            arr.append(float(value))
            if len(arr) > 5000:
                del arr[: len(arr) - 5000]

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "hist": {k: list(v) for k, v in self._hist.items()},
            }

    def render_prometheus(self) -> str:
        s = self.snapshot()
        lines: list[str] = []
        for k, v in sorted((s.get("counters") or {}).items()):
            name = _metric_name(k)
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {float(v):.6f}")
        for k, v in sorted((s.get("gauges") or {}).items()):
            name = _metric_name(k)
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {float(v):.6f}")
        for k, values in sorted((s.get("hist") or {}).items()):
            name = _metric_name(k)
            if not values:
                continue
            arr = sorted(float(x) for x in values)
            count = len(arr)
            total = sum(arr)
            lines.append(f"# TYPE {name}_seconds summary")
            for q in (0.5, 0.9, 0.95, 0.99):
                idx = min(count - 1, max(0, int(q * (count - 1))))
                lines.append(f'{name}_seconds{{quantile="{q}"}} {arr[idx]:.6f}')
            lines.append(f"{name}_seconds_sum {total:.6f}")
            lines.append(f"{name}_seconds_count {count}")
        lines.append(f'process_time_seconds {time.time():.6f}')
        return "\n".join(lines) + "\n"


def _metric_name(name: str) -> str:
    out = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in str(name))
    if not out:
        out = "metric"
    if out[0].isdigit():
        out = f"m_{out}"
    return out
