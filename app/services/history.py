import json
import sqlite3
import threading
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings

DEFAULT_TITLE = "新会话"


class HistoryStore:
    def __init__(self, base_dir: Path | None = None):
        settings = get_settings()
        self._backend = str(getattr(settings, "history_backend", "file") or "file").strip().lower()
        if self._backend not in {"file", "sqlite"}:
            self._backend = "file"
        self.base_dir = base_dir or settings.sessions_path
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self._cold_dir = settings.history_cold_path / self.base_dir.name
        self._cold_dir.mkdir(parents=True, exist_ok=True)
        self._hot_days = max(1, int(getattr(settings, "history_hot_tier_days", 14) or 14))
        self._db_path = settings.history_sqlite_path
        self._namespace = str(self.base_dir.resolve())
        self._lock = threading.RLock()
        self._last_tier_ts = 0.0
        if self._backend == "sqlite":
            self._init_sqlite()

    def create_session(self, title: str | None = None, session_id: str | None = None) -> dict[str, Any]:
        session_id = session_id or uuid.uuid4().hex
        now = self._now()
        data = {
            "session_id": session_id,
            "title": title or DEFAULT_TITLE,
            "created_at": now,
            "updated_at": now,
            "messages": [],
            "runtime_policy": {"strategy_lock": None},
        }
        self._write(session_id, data)
        return data

    def get_or_create_session(self, session_id: str | None = None) -> dict[str, Any]:
        if session_id:
            existing = self.get_session(session_id)
            if existing is not None:
                return existing
            return self.create_session(session_id=session_id)
        return self.create_session()

    def list_sessions(self) -> list[dict[str, Any]]:
        items: list[dict[str, Any]] = []
        for data in self._iter_sessions_data():
            items.append(
                {
                    "session_id": data.get("session_id", ""),
                    "title": data.get("title", DEFAULT_TITLE),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at"),
                    "message_count": len(data.get("messages", [])),
                }
            )
        items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        return items

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        data = self._read(session_id)
        if data is None:
            return None
        if self._ensure_message_ids(data):
            self._write(session_id, data)
        return data

    def get_session_strategy_lock(self, session_id: str) -> str | None:
        data = self.get_session(session_id)
        if data is None:
            return None
        policy = data.get("runtime_policy", {}) or {}
        value = str(policy.get("strategy_lock", "") or "").strip().lower()
        return value or None

    def set_session_strategy_lock(self, session_id: str, strategy: str | None) -> dict[str, Any] | None:
        data = self.get_session(session_id)
        if data is None:
            return None
        policy = dict(data.get("runtime_policy", {}) or {})
        policy["strategy_lock"] = str(strategy or "").strip().lower() or None
        data["runtime_policy"] = policy
        data["updated_at"] = self._now()
        self._write(session_id, data)
        return data

    def delete_session(self, session_id: str) -> bool:
        if self._backend == "sqlite":
            with self._lock, self._connect() as conn:
                cur = conn.execute("DELETE FROM sessions WHERE namespace=? AND session_id=?", (self._namespace, session_id))
                conn.commit()
                return int(cur.rowcount or 0) > 0
        path = self.base_dir / f"{session_id}.json"
        if not path.exists():
            return False
        path.unlink()
        return True

    def append_message(self, session_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        data = self.get_or_create_session(session_id)
        if not data.get("messages") and role == "user":
            title = (content or DEFAULT_TITLE).strip().replace("\n", " ")[:40]
            data["title"] = title or data.get("title", DEFAULT_TITLE)
        data.setdefault("messages", []).append(
            {
                "message_id": uuid.uuid4().hex,
                "role": role,
                "content": content,
                "metadata": metadata or {},
                "created_at": self._now(),
            }
        )
        data["updated_at"] = self._now()
        self._write(data["session_id"], data)
        return data

    def update_message(self, session_id: str, message_id: str, content: str) -> dict[str, Any] | None:
        data = self.get_session(session_id)
        if data is None:
            return None
        if self._update_message_in_data(data, message_id, content) is None:
            return None
        data["updated_at"] = self._now()
        self._refresh_title(data)
        self._write(session_id, data)
        return data

    def get_message(self, session_id: str, message_id: str) -> dict[str, Any] | None:
        data = self.get_session(session_id)
        if data is None:
            return None
        self._ensure_message_ids(data)
        for msg in data.get("messages", []):
            if msg.get("message_id") == message_id:
                return msg
        return None

    def upsert_assistant_after_user(
        self,
        session_id: str,
        user_message_id: str,
        assistant_content: str,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        data = self.get_session(session_id)
        if data is None:
            return None
        self._ensure_message_ids(data)
        messages = data.get("messages", [])
        for idx, msg in enumerate(messages):
            if msg.get("message_id") != user_message_id:
                continue
            if msg.get("role") != "user":
                return None
            candidate_idx = idx + 1
            if candidate_idx < len(messages) and messages[candidate_idx].get("role") == "assistant":
                messages[candidate_idx]["content"] = assistant_content
                messages[candidate_idx]["metadata"] = metadata or {}
                messages[candidate_idx]["updated_at"] = self._now()
            else:
                messages.insert(
                    candidate_idx,
                    {
                        "message_id": uuid.uuid4().hex,
                        "role": "assistant",
                        "content": assistant_content,
                        "metadata": metadata or {},
                        "created_at": self._now(),
                    },
                )
            data["updated_at"] = self._now()
            self._write(session_id, data)
            return data
        return None

    def delete_message(self, session_id: str, message_id: str) -> dict[str, Any] | None:
        data = self.get_session(session_id)
        if data is None:
            return None
        messages = data.get("messages", [])
        self._ensure_message_ids(data)
        kept = [m for m in messages if m.get("message_id") != message_id]
        if len(kept) == len(messages):
            return None
        data["messages"] = kept
        data["updated_at"] = self._now()
        self._refresh_title(data)
        self._write(session_id, data)
        return data

    def _refresh_title(self, data: dict[str, Any]) -> None:
        for msg in data.get("messages", []):
            if msg.get("role") == "user":
                title = (msg.get("content") or DEFAULT_TITLE).strip().replace("\n", " ")[:40]
                data["title"] = title or DEFAULT_TITLE
                return
        data["title"] = DEFAULT_TITLE

    def _update_message_in_data(self, data: dict[str, Any], message_id: str, content: str) -> dict[str, Any] | None:
        self._ensure_message_ids(data)
        for msg in data.get("messages", []):
            if msg.get("message_id") != message_id:
                continue
            msg["content"] = content
            msg["updated_at"] = self._now()
            return msg
        return None

    def _ensure_message_ids(self, data: dict[str, Any]) -> bool:
        changed = False
        for msg in data.get("messages", []):
            if not msg.get("message_id"):
                msg["message_id"] = uuid.uuid4().hex
                changed = True
        return changed

    def _write(self, session_id: str, data: dict[str, Any]) -> None:
        if self._backend == "sqlite":
            created_at = str(data.get("created_at") or self._now())
            updated_at = str(data.get("updated_at") or self._now())
            payload = json.dumps(data, ensure_ascii=False)
            with self._lock, self._connect() as conn:
                updated = conn.execute(
                    "UPDATE sessions SET data_json=?, updated_at=? WHERE namespace=? AND session_id=?",
                    (payload, updated_at, self._namespace, session_id),
                )
                if int(updated.rowcount or 0) == 0:
                    conn.execute(
                    """
                    INSERT INTO sessions(namespace, session_id, data_json, created_at, updated_at)
                    VALUES(?, ?, ?, ?, ?)
                    """,
                    (self._namespace, session_id, payload, created_at, updated_at),
                )
                conn.commit()
            return
        path = self.base_dir / f"{session_id}.json"
        temp_path = path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)
        self._tier_cold_files_if_needed()

    def _read(self, session_id: str) -> dict[str, Any] | None:
        if self._backend == "sqlite":
            with self._lock, self._connect() as conn:
                row = conn.execute(
                    "SELECT data_json FROM sessions WHERE namespace=? AND session_id=?",
                    (self._namespace, session_id),
                ).fetchone()
            if not row:
                return None
            try:
                data = json.loads(str(row[0] or ""))
            except Exception:
                return None
            return data if isinstance(data, dict) else None
        path = self.base_dir / f"{session_id}.json"
        if not path.exists():
            cold_path = self._cold_dir / f"{session_id}.json"
            if cold_path.exists():
                path = cold_path
            else:
                return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None
        return data if isinstance(data, dict) else None

    def _iter_sessions_data(self) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        if self._backend == "sqlite":
            with self._lock, self._connect() as conn:
                out = conn.execute(
                    "SELECT data_json FROM sessions WHERE namespace=? ORDER BY updated_at DESC",
                    (self._namespace,),
                ).fetchall()
            for row in out:
                try:
                    data = json.loads(str(row[0] or ""))
                except Exception:
                    continue
                if isinstance(data, dict):
                    rows.append(data)
            return rows
        for path in sorted(self.base_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(data, dict):
                rows.append(data)
        for path in sorted(self._cold_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(data, dict):
                rows.append(data)
        return rows

    def _tier_cold_files_if_needed(self) -> None:
        if self._backend != "file":
            return
        now_ts = datetime.now(timezone.utc).timestamp()
        if (now_ts - self._last_tier_ts) < 300:
            return
        self._last_tier_ts = now_ts
        cutoff = datetime.now(timezone.utc) - timedelta(days=self._hot_days)
        for path in list(self.base_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            updated = str(data.get("updated_at", "") or "")
            try:
                dt = datetime.fromisoformat(updated) if updated else datetime.now(timezone.utc)
            except Exception:
                dt = datetime.now(timezone.utc)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            else:
                dt = dt.astimezone(timezone.utc)
            if dt < cutoff:
                target = self._cold_dir / path.name
                try:
                    path.replace(target)
                except Exception:
                    continue

    def _connect(self) -> sqlite3.Connection:
        settings = get_settings()
        timeout_s = max(1.0, float(getattr(settings, "sqlite_busy_timeout_seconds", 10) or 10))
        conn = sqlite3.connect(self._db_path, timeout=timeout_s)
        conn.execute(f"PRAGMA busy_timeout = {int(timeout_s * 1000)}")
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_sqlite(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS sessions(
                    namespace TEXT NOT NULL DEFAULT '',
                    session_id TEXT NOT NULL,
                    data_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY(namespace, session_id)
                )
                """
            )
            cols = [str(r[1]) for r in conn.execute("PRAGMA table_info(sessions)").fetchall()]
            if "namespace" not in cols:
                conn.execute("ALTER TABLE sessions ADD COLUMN namespace TEXT NOT NULL DEFAULT ''")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_sessions_ns_updated_at ON sessions(namespace, updated_at)")
            conn.commit()

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
