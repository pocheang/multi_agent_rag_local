from __future__ import annotations

import logging
import threading
import traceback
from collections import deque
from datetime import UTC, datetime
from typing import Any

from app.domain.text import normalize_string

_LOCK = threading.Lock()
_BUFFER: deque[dict[str, Any]] = deque(maxlen=4000)
_INSTALLED = False


class InMemoryLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            created = datetime.fromtimestamp(float(record.created), tz=UTC).isoformat()
        except (ValueError, OSError):
            # Invalid timestamp, use current time
            created = datetime.now(UTC).isoformat()
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
    level_lc = normalize_string(level, lowercase=True)
    logger_lc = normalize_string(logger_keyword, lowercase=True)
    keyword_lc = normalize_string(keyword, lowercase=True)
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


def list_log_levels() -> dict[str, Any]:
    """Return configured levels for active loggers and the root logger."""
    loggers: dict[str, str] = {}
    for name in sorted(logging.Logger.manager.loggerDict.keys()):
        logger = logging.getLogger(name)
        if logger.level != logging.NOTSET:
            loggers[name] = str(logging.getLevelName(logger.level))
    root = logging.getLogger()
    loggers["root"] = str(logging.getLevelName(root.level))
    return {
        "loggers": loggers,
        "total_loggers": len(loggers),
        "available_levels": ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    }


def set_logger_level(*, logger_name: str, level: str) -> dict[str, Any]:
    """Set one logger's level, or the root level when ``logger_name`` is root."""
    if not logger_name:
        raise ValueError("logger name is required")
    if level not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}:
        raise ValueError(f"Invalid log level: {level}")
    numeric_level = getattr(logging, level)
    if logger_name == "root":
        logging.getLogger().setLevel(numeric_level)
        affected_logger = "root (all loggers)"
    else:
        logging.getLogger(logger_name).setLevel(numeric_level)
        affected_logger = logger_name
    return {
        "ok": True,
        "logger": affected_logger,
        "level": level,
        "message": f"Log level for '{affected_logger}' set to {level}",
    }


def reset_logger_levels() -> dict[str, Any]:
    """Restore root INFO and let explicitly configured loggers inherit it."""
    logging.getLogger().setLevel(logging.INFO)
    reset_count = 0
    for name in logging.Logger.manager.loggerDict.keys():
        logger = logging.getLogger(name)
        if logger.level != logging.NOTSET:
            logger.setLevel(logging.NOTSET)
            reset_count += 1
    return {
        "ok": True,
        "reset_count": reset_count,
        "message": f"Reset {reset_count} loggers to default levels",
    }
