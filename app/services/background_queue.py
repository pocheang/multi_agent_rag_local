from __future__ import annotations

from collections.abc import Callable
import logging
from queue import Empty, Full, Queue
import threading
import time
from typing import Any

logger = logging.getLogger(__name__)


class BackgroundTaskQueue:
    def __init__(self, *, maxsize: int, workers: int, name: str = "background"):
        self._queue: Queue[tuple[Callable[..., Any], tuple[Any, ...], dict[str, Any]]] = Queue(maxsize=max(1, int(maxsize)))
        self._workers: list[threading.Thread] = []
        self._stop_event = threading.Event()
        self._worker_count = max(1, int(workers))
        self._name = name
        self._started = False

    def start(self) -> None:
        if self._started:
            self._workers = [t for t in self._workers if t.is_alive()]
            if self._workers:
                return
            self._started = False
        self._started = True
        self._stop_event.clear()
        for i in range(self._worker_count):
            t = threading.Thread(
                target=self._run,
                daemon=True,
                name=f"{self._name}-worker-{i + 1}",
            )
            t.start()
            self._workers.append(t)

    def stop(self, timeout: float = 2.0, drain: bool = True) -> None:
        if not self._started:
            return
        self._stop_event.set()
        if drain:
            deadline = time.monotonic() + max(0.0, float(timeout))
            while self._queue.unfinished_tasks > 0 and time.monotonic() < deadline:
                time.sleep(0.05)
        alive: list[threading.Thread] = []
        for t in self._workers:
            t.join(timeout=timeout)
            if t.is_alive():
                alive.append(t)
        self._workers = alive
        if alive:
            logger.warning("background queue stop timed out; %s workers still alive", len(alive))
        self._started = bool(self._workers)

    def submit(self, fn: Callable[..., Any], *args: Any, **kwargs: Any) -> bool:
        try:
            self._queue.put_nowait((fn, args, kwargs))
            return True
        except Full:
            return False

    def stats(self) -> dict[str, int]:
        return {
            "queue_size": int(self._queue.qsize()),
            "max_queue_size": int(self._queue.maxsize),
            "workers": len(self._workers),
        }

    def _run(self) -> None:
        while True:
            try:
                fn, args, kwargs = self._queue.get(timeout=0.5)
            except Empty:
                if self._stop_event.is_set():
                    break
                continue
            try:
                fn(*args, **kwargs)
            except Exception:
                logger.exception("background task failed")
            finally:
                self._queue.task_done()
