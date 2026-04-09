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
                  agent_class TEXT NOT NULL DEFAULT 'general',
                  created_at TEXT NOT NULL,
                  updated_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prompt_templates_user ON prompt_templates(user_id)")
            rows = conn.execute("PRAGMA table_info(prompt_templates)").fetchall()
            cols = {str(r[1]) for r in rows}
            if "agent_class" not in cols:
                conn.execute("ALTER TABLE prompt_templates ADD COLUMN agent_class TEXT NOT NULL DEFAULT 'general'")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS prompt_template_versions (
                  version_id TEXT PRIMARY KEY,
                  prompt_id TEXT NOT NULL,
                  user_id TEXT NOT NULL,
                  title TEXT NOT NULL,
                  content TEXT NOT NULL,
                  agent_class TEXT NOT NULL DEFAULT 'general',
                  change_note TEXT,
                  status TEXT NOT NULL DEFAULT 'draft',
                  approved_by TEXT,
                  approved_at TEXT,
                  created_at TEXT NOT NULL
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS idx_prompt_versions_prompt ON prompt_template_versions(prompt_id, created_at DESC)")

    def list_prompts(self, user_id: str) -> list[dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT prompt_id, title, content, agent_class, created_at, updated_at
                FROM prompt_templates
                WHERE user_id=?
                ORDER BY updated_at DESC
                """,
                (user_id,),
            ).fetchall()
            return [dict(r) for r in rows]

    def create_prompt(self, user_id: str, title: str, content: str, agent_class: str = "general") -> dict[str, Any]:
        prompt_id = uuid.uuid4().hex
        now = _now_iso()
        cls = (agent_class or "general").strip() or "general"
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO prompt_templates(prompt_id, user_id, title, content, agent_class, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (prompt_id, user_id, title, content, cls, now, now),
            )
            self._insert_version(
                conn,
                prompt_id=prompt_id,
                user_id=user_id,
                title=title,
                content=content,
                agent_class=cls,
                change_note="initial_create",
            )
        return {"prompt_id": prompt_id, "title": title, "content": content, "agent_class": cls, "created_at": now, "updated_at": now}

    def update_prompt(
        self,
        user_id: str,
        prompt_id: str,
        title: str,
        content: str,
        agent_class: str = "general",
    ) -> dict[str, Any] | None:
        now = _now_iso()
        cls = (agent_class or "general").strip() or "general"
        with self._connect() as conn:
            result = conn.execute(
                """
                UPDATE prompt_templates
                SET title=?, content=?, agent_class=?, updated_at=?
                WHERE prompt_id=? AND user_id=?
                """,
                (title, content, cls, now, prompt_id, user_id),
            )
            if result.rowcount <= 0:
                return None
            self._insert_version(
                conn,
                prompt_id=prompt_id,
                user_id=user_id,
                title=title,
                content=content,
                agent_class=cls,
                change_note="update",
            )
            row = conn.execute(
                """
                SELECT prompt_id, title, content, agent_class, created_at, updated_at
                FROM prompt_templates
                WHERE prompt_id=? AND user_id=?
                """,
                (prompt_id, user_id),
            ).fetchone()
            return dict(row) if row else None

    def list_versions(self, user_id: str, prompt_id: str, limit: int = 20) -> list[dict[str, Any]]:
        cap = max(1, min(int(limit), 200))
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT version_id, prompt_id, title, content, agent_class, change_note, status, approved_by, approved_at, created_at
                FROM prompt_template_versions
                WHERE user_id=? AND prompt_id=?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, prompt_id, cap),
            ).fetchall()
            return [dict(r) for r in rows]

    def approve_version(self, user_id: str, prompt_id: str, version_id: str, approved_by: str) -> dict[str, Any] | None:
        now = _now_iso()
        with self._connect() as conn:
            res = conn.execute(
                """
                UPDATE prompt_template_versions
                SET status='approved', approved_by=?, approved_at=?
                WHERE user_id=? AND prompt_id=? AND version_id=?
                """,
                (approved_by, now, user_id, prompt_id, version_id),
            )
            if res.rowcount <= 0:
                return None
            row = conn.execute(
                """
                SELECT version_id, prompt_id, title, content, agent_class, change_note, status, approved_by, approved_at, created_at
                FROM prompt_template_versions
                WHERE version_id=?
                """,
                (version_id,),
            ).fetchone()
            return dict(row) if row else None

    def rollback_to_version(self, user_id: str, prompt_id: str, version_id: str) -> dict[str, Any] | None:
        now = _now_iso()
        with self._connect() as conn:
            row = conn.execute(
                """
                SELECT title, content, agent_class
                FROM prompt_template_versions
                WHERE user_id=? AND prompt_id=? AND version_id=?
                """,
                (user_id, prompt_id, version_id),
            ).fetchone()
            if row is None:
                return None
            result = conn.execute(
                """
                UPDATE prompt_templates
                SET title=?, content=?, agent_class=?, updated_at=?
                WHERE user_id=? AND prompt_id=?
                """,
                (str(row["title"]), str(row["content"]), str(row["agent_class"]), now, user_id, prompt_id),
            )
            if result.rowcount <= 0:
                return None
            self._insert_version(
                conn,
                prompt_id=prompt_id,
                user_id=user_id,
                title=str(row["title"]),
                content=str(row["content"]),
                agent_class=str(row["agent_class"]),
                change_note=f"rollback_from:{version_id}",
            )
            current = conn.execute(
                """
                SELECT prompt_id, title, content, agent_class, created_at, updated_at
                FROM prompt_templates
                WHERE user_id=? AND prompt_id=?
                """,
                (user_id, prompt_id),
            ).fetchone()
            return dict(current) if current else None

    def _insert_version(
        self,
        conn: sqlite3.Connection,
        *,
        prompt_id: str,
        user_id: str,
        title: str,
        content: str,
        agent_class: str,
        change_note: str,
    ) -> None:
        version_id = uuid.uuid4().hex
        created_at = _now_iso()
        conn.execute(
            """
            INSERT INTO prompt_template_versions(
              version_id, prompt_id, user_id, title, content, agent_class, change_note, status, approved_by, approved_at, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, 'draft', NULL, NULL, ?)
            """,
            (version_id, prompt_id, user_id, title, content, agent_class, change_note, created_at),
        )

    def delete_prompt(self, user_id: str, prompt_id: str) -> bool:
        with self._connect() as conn:
            result = conn.execute("DELETE FROM prompt_templates WHERE prompt_id=? AND user_id=?", (prompt_id, user_id))
            return result.rowcount > 0
