from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
import logging
import threading
import traceback
from typing import Any

_LOCK = threading.Lock()
_BUFFER: deque[dict[str, Any]] = deque(maxlen=4000)
_INSTALLED = False


class InMemoryLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            created = datetime.fromtimestamp(float(record.created), tz=timezone.utc).isoformat()
        except Exception:
            created = datetime.now(timezone.utc).isoformat()
        message = str(record.getMessage() or "")
        exc_text = ""
        if record.exc_info:
            exc_text = "".join(traceback.format_exception(*record.exc_info))
        row = {
            "created_at": created,
            "level": str(record.levelname or ""),
            "logger": str(record.name or ""),
            "message": message,
            "module": str(record.module or ""),
            "func": str(record.funcName or ""),
            "line": int(record.lineno or 0),
            "thread": str(record.threadName or ""),
            "exception": exc_text,
        }
        with _LOCK:
            _BUFFER.append(row)


def setup_log_capture() -> None:
    global _INSTALLED
    with _LOCK:
        if _INSTALLED:
            return
        handler = InMemoryLogHandler()
        handler.setLevel(logging.INFO)
        root = logging.getLogger()
        root.addHandler(handler)
        logging.getLogger("uvicorn.error").addHandler(handler)
        logging.getLogger("uvicorn.access").addHandler(handler)
        _INSTALLED = True


def list_captured_logs(
    *,
    limit: int = 200,
    level: str | None = None,
    logger_keyword: str | None = None,
    keyword: str | None = None,
) -> list[dict[str, Any]]:
    cap = max(1, min(int(limit or 200), 1000))
    level_lc = str(level or "").strip().lower()
    logger_lc = str(logger_keyword or "").strip().lower()
    keyword_lc = str(keyword or "").strip().lower()
    with _LOCK:
        rows = list(_BUFFER)
    out: list[dict[str, Any]] = []
    for row in reversed(rows):
        if level_lc and str(row.get("level", "")).lower() != level_lc:
            continue
        if logger_lc and logger_lc not in str(row.get("logger", "")).lower():
            continue
        if keyword_lc:
            hay = f"{row.get('message', '')}\n{row.get('exception', '')}".lower()
            if keyword_lc not in hay:
                continue
        out.append(row)
        if len(out) >= cap:
            break
    return out

