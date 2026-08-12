from __future__ import annotations

import threading
import time
from typing import Any


class RuntimeMetrics:
    """
    Enhanced runtime metrics collector with label support.

    Supports Prometheus-style metrics with labels for better dimensionality.
    """

    def __init__(self):
        self._lock = threading.Lock()
        # Legacy flat metrics (backward compatible)
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._hist: dict[str, list[float]] = {}

        # New labeled metrics (metric_name -> {label_key: {label_value: value}})
        self._labeled_counters: dict[str, dict[str, dict[str, float]]] = {}
        self._labeled_gauges: dict[str, dict[str, dict[str, float]]] = {}
        self._labeled_hist: dict[str, dict[str, dict[str, list[float]]]] = {}

    def inc(self, name: str, value: float = 1.0, labels: dict[str, str] | None = None) -> None:
        """Increment a counter, optionally with labels."""
        with self._lock:
            if labels:
                # Labeled counter
                if name not in self._labeled_counters:
                    self._labeled_counters[name] = {}

                for label_key, label_value in labels.items():
                    if label_key not in self._labeled_counters[name]:
                        self._labeled_counters[name][label_key] = {}

                    current = self._labeled_counters[name][label_key].get(label_value, 0.0)
                    self._labeled_counters[name][label_key][label_value] = float(current + value)
            else:
                # Legacy flat counter
                self._counters[name] = float(self._counters.get(name, 0.0) + value)

    def set_gauge(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Set a gauge value, optionally with labels."""
        with self._lock:
            if labels:
                # Labeled gauge
                if name not in self._labeled_gauges:
                    self._labeled_gauges[name] = {}

                for label_key, label_value in labels.items():
                    if label_key not in self._labeled_gauges[name]:
                        self._labeled_gauges[name][label_key] = {}

                    self._labeled_gauges[name][label_key][label_value] = float(value)
            else:
                # Legacy flat gauge
                self._gauges[name] = float(value)

    def observe(self, name: str, value: float, labels: dict[str, str] | None = None) -> None:
        """Record a histogram observation, optionally with labels."""
        with self._lock:
            if labels:
                # Labeled histogram
                if name not in self._labeled_hist:
                    self._labeled_hist[name] = {}

                for label_key, label_value in labels.items():
                    if label_key not in self._labeled_hist[name]:
                        self._labeled_hist[name][label_key] = {}

                    if label_value not in self._labeled_hist[name][label_key]:
                        self._labeled_hist[name][label_key][label_value] = []

                    arr = self._labeled_hist[name][label_key][label_value]
                    arr.append(float(value))
                    if len(arr) > 5000:
                        del arr[: len(arr) - 5000]
            else:
                # Legacy flat histogram
                arr = self._hist.setdefault(name, [])
                arr.append(float(value))
                if len(arr) > 5000:
                    del arr[: len(arr) - 5000]

    def inc_agent_execution(self, agent_name: str, status: str, route: str | None = None) -> None:
        """Business metric: Increment agent execution counter."""
        labels = {"agent": agent_name, "status": status}
        if route:
            labels["route"] = route
        self.inc("agent_execution_total", 1.0, labels)

    def observe_retrieval_quality(self, score: float, strategy: str) -> None:
        """Business metric: Record retrieval quality score."""
        self.observe("retrieval_quality_score", score, {"strategy": strategy})

    def inc_llm_cost(self, cost_usd: float, provider: str, model: str) -> None:
        """Business metric: Track LLM API costs."""
        self.inc("llm_api_cost_usd_total", cost_usd, {"provider": provider, "model": model})

    def inc_cache_operations(self, operation: str, hit: bool, layer: str) -> None:
        """Business metric: Track cache hit/miss by layer."""
        labels = {"operation": operation, "result": "hit" if hit else "miss", "layer": layer}
        self.inc("cache_operations_total", 1.0, labels)

    def observe_session_duration(self, duration_seconds: float, user_type: str) -> None:
        """Business metric: Track user session duration."""
        self.observe("user_session_duration_seconds", duration_seconds, {"user_type": user_type})

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "hist": {k: list(v) for k, v in self._hist.items()},
                "labeled_counters": {
                    name: {label_key: dict(values) for label_key, values in labels.items()}
                    for name, labels in self._labeled_counters.items()
                },
                "labeled_gauges": {
                    name: {label_key: dict(values) for label_key, values in labels.items()}
                    for name, labels in self._labeled_gauges.items()
                },
                "labeled_hist": {
                    name: {
                        label_key: {label_value: list(arr) for label_value, arr in values.items()}
                        for label_key, values in labels.items()
                    }
                    for name, labels in self._labeled_hist.items()
                },
            }

    def render_prometheus(self) -> str:
        s = self.snapshot()
        lines: list[str] = []

        # Legacy flat counters
        for k, v in sorted((s.get("counters") or {}).items()):
            name = _metric_name(k)
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {float(v):.6f}")

        # Labeled counters
        for metric_name, label_data in sorted((s.get("labeled_counters") or {}).items()):
            prom_name = _metric_name(metric_name)
            lines.append(f"# TYPE {prom_name} counter")
            for label_key, label_values in sorted(label_data.items()):
                for label_value, count in sorted(label_values.items()):
                    label_str = f'{label_key}="{label_value}"'
                    lines.append(f"{prom_name}{{{label_str}}} {float(count):.6f}")

        # Legacy flat gauges
        for k, v in sorted((s.get("gauges") or {}).items()):
            name = _metric_name(k)
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {float(v):.6f}")

        # Labeled gauges
        for metric_name, label_data in sorted((s.get("labeled_gauges") or {}).items()):
            prom_name = _metric_name(metric_name)
            lines.append(f"# TYPE {prom_name} gauge")
            for label_key, label_values in sorted(label_data.items()):
                for label_value, gauge_value in sorted(label_values.items()):
                    label_str = f'{label_key}="{label_value}"'
                    lines.append(f"{prom_name}{{{label_str}}} {float(gauge_value):.6f}")

        # Legacy flat histograms
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

        # Labeled histograms
        for metric_name, label_data in sorted((s.get("labeled_hist") or {}).items()):
            prom_name = _metric_name(metric_name)
            lines.append(f"# TYPE {prom_name}_seconds summary")
            for label_key, label_values in sorted(label_data.items()):
                for label_value, values in sorted(label_values.items()):
                    if not values:
                        continue
                    arr = sorted(float(x) for x in values)
                    count = len(arr)
                    total = sum(arr)
                    label_str = f'{label_key}="{label_value}"'
                    for q in (0.5, 0.9, 0.95, 0.99):
                        idx = min(count - 1, max(0, int(q * (count - 1))))
                        lines.append(f'{prom_name}_seconds{{quantile="{q}",{label_str}}} {arr[idx]:.6f}')
                    lines.append(f"{prom_name}_seconds_sum{{{label_str}}} {total:.6f}")
                    lines.append(f"{prom_name}_seconds_count{{{label_str}}} {count}")

        lines.append(f"process_time_seconds {time.time():.6f}")
        return "\n".join(lines) + "\n"


def _metric_name(name: str) -> str:
    out = "".join(ch if (ch.isalnum() or ch == "_") else "_" for ch in str(name))
    if not out:
        out = "metric"
    if out[0].isdigit():
        out = f"m_{out}"
    return out


