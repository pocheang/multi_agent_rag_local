import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class PromptStore:
    def __init__(self, db_path: Path | None = None):
        settings = get_settings()
        self.db_path = db_path or settings.app_db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS prompt_templates (
                  prompt_id TEXT PRIMARY KEY,
                  user_id TEXT NOT NULL,
                  title TEXT NOT NULL,
                  content TEXT NOT NULL,
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prompt_templates_user ON prompt_templates(user_id)")

    def list_prompts(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT prompt_id, title, content, created_at, updated_at
                FROM prompt_templates
                WHERE user_id=?
                ORDER BY updated_at DESC
                """,
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def create_prompt(self, user_id: str, title: str, content: str) -> dict[str, Any]:
        prompt_id = uuid.uuid4().hex
        now = _now_iso()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO prompt_templates(prompt_id, user_id, title, content, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (prompt_id, user_id, title, content, now, now),
            )
        return {"prompt_id": prompt_id, "title": title, "content": content, "created_at": now, "updated_at": now}

    def update_prompt(self, user_id: str, prompt_id: str, title: str, content: str) -> dict[str, Any] | None:
        now = _now_iso()
        with self._connect() as conn:
            result = conn.execute(
                """
                UPDATE prompt_templates
                SET title=?, content=?, updated_at=?
                WHERE prompt_id=? AND user_id=?
                """,
                (title, content, now, prompt_id, user_id),
            )
            if result.rowcount <= 0:
                return None
            row = conn.execute(
                """
                SELECT prompt_id, title, content, created_at, updated_at
                FROM prompt_templates
                WHERE prompt_id=? AND user_id=?
                """,
                (prompt_id, user_id),
            ).fetchone()
            return dict(row) if row else None

    def delete_prompt(self, user_id: str, prompt_id: str) -> bool:
        with self._connect() as conn:
            result = conn.execute("DELETE FROM prompt_templates WHERE prompt_id=? AND user_id=?", (prompt_id, user_id))
            return result.rowcount > 0
