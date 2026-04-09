import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings


class HistoryStore:
    def __init__(self, base_dir: Path | None = None):
        settings = get_settings()
        self.base_dir = base_dir or settings.sessions_path
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def create_session(self, title: str | None = None, session_id: str | None = None) -> dict[str, Any]:
        session_id = session_id or uuid.uuid4().hex
        now = self._now()
        data = {
            "session_id": session_id,
            "title": title or "新会话",
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
        for path in sorted(self.base_dir.glob("*.json"), reverse=True):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            items.append(
                {
                    "session_id": data.get("session_id", path.stem),
                    "title": data.get("title", "新会话"),
                    "created_at": data.get("created_at"),
                    "updated_at": data.get("updated_at"),
                    "message_count": len(data.get("messages", [])),
                }
            )
        items.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
        return items

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        path = self.base_dir / f"{session_id}.json"
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
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
        path = self.base_dir / f"{session_id}.json"
        if not path.exists():
            return False
        path.unlink()
        return True

    def append_message(self, session_id: str, role: str, content: str, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        data = self.get_or_create_session(session_id)
        if not data.get("messages") and role == "user":
            title = (content or "新会话").strip().replace("\n", " ")[:40]
            data["title"] = title or data.get("title", "新会话")
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
                title = (msg.get("content") or "新会话").strip().replace("\n", " ")[:40]
                data["title"] = title or "新会话"
                return
        data["title"] = "新会话"

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
        path = self.base_dir / f"{session_id}.json"
        temp_path = path.with_suffix(".json.tmp")
        temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
