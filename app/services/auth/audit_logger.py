import threading
import uuid
from typing import Any

from app.services.alerting import resolve_signing_secret, sign_payload
from app.services.auth.utils import now, iso


def classify_audit_event(action: str, result: str) -> tuple[str, str]:
    action_lc = (action or "").strip().lower()
    result_lc = (result or "").strip().lower()

    if action_lc.startswith("auth."):
        category = "auth"
    elif action_lc.startswith("query.") or action_lc.startswith("document."):
        category = "data"
    elif action_lc.startswith("admin."):
        category = "admin"
    elif action_lc.startswith("prompt."):
        category = "prompt"
    else:
        category = "system"

    if result_lc == "failed":
        severity = "high"
    elif result_lc == "denied":
        severity = "medium"
    else:
        severity = "info"
    return category, severity


class AuditLogger:
    def __init__(self, conn_factory):
        self.conn_factory = conn_factory
        self._audit_lock = threading.Lock()

    def add_audit_log(
        self,
        action: str,
        resource_type: str,
        result: str,
        actor_user_id: str | None = None,
        actor_role: str | None = None,
        resource_id: str | None = None,
        ip: str | None = None,
        user_agent: str | None = None,
        detail: str | None = None,
    ) -> dict[str, Any]:
        event_id = uuid.uuid4().hex
        created_at = iso(now())
        event_category, severity = classify_audit_event(action=action, result=result)
        hash_kid, hash_secret = resolve_signing_secret()
        prev_event_hash = None
        event_hash = None
        with self._audit_lock:
            with self.conn_factory() as conn:
                conn.execute("BEGIN IMMEDIATE")
                prev_row = conn.execute(
                    "SELECT event_hash FROM audit_logs WHERE event_hash IS NOT NULL AND event_hash <> '' ORDER BY created_at DESC, event_id DESC LIMIT 1"
                ).fetchone()
                prev_event_hash = str(prev_row["event_hash"]) if prev_row and prev_row["event_hash"] else None
                if hash_secret:
                    event_hash = sign_payload(
                        {
                            "event_id": event_id,
                            "created_at": created_at,
                            "prev_event_hash": prev_event_hash or "",
                            "actor_user_id": actor_user_id or "",
                            "actor_role": actor_role or "",
                            "action": action,
                            "event_category": event_category or "",
                            "severity": severity or "",
                            "resource_type": resource_type,
                            "resource_id": resource_id or "",
                            "result": result,
                            "ip": ip or "",
                            "user_agent": user_agent or "",
                            "detail": detail or "",
                        },
                        hash_secret,
                    )
                conn.execute(
                    """
                    INSERT INTO audit_logs(
                        event_id, actor_user_id, actor_role, action, event_category, severity,
                        resource_type, resource_id, result, ip, user_agent, detail, created_at,
                        prev_event_hash, event_hash, hash_kid
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event_id,
                        actor_user_id,
                        actor_role,
                        action,
                        event_category,
                        severity,
                        resource_type,
                        resource_id,
                        result,
                        ip,
                        user_agent,
                        detail,
                        created_at,
                        prev_event_hash,
                        event_hash,
                        hash_kid,
                    ),
                )
                conn.commit()
        return {
            "event_id": event_id,
            "actor_user_id": actor_user_id,
            "actor_role": actor_role,
            "action": action,
            "event_category": event_category,
            "severity": severity,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "result": result,
            "ip": ip,
            "user_agent": user_agent,
            "detail": detail,
            "created_at": created_at,
            "prev_event_hash": prev_event_hash,
            "event_hash": event_hash,
            "hash_kid": hash_kid,
        }

    def list_audit_logs(
        self,
        limit: int = 200,
        actor_user_id: str | None = None,
        action_keyword: str | None = None,
        event_category: str | None = None,
        severity: str | None = None,
        result: str | None = None,
    ) -> list[dict[str, Any]]:
        cap = max(1, min(limit, 1000))
        where: list[str] = []
        params: list[Any] = []
        actor = (actor_user_id or "").strip()
        keyword = (action_keyword or "").strip().lower()
        category = (event_category or "").strip().lower()
        sev = (severity or "").strip().lower()
        res = (result or "").strip().lower()

        if actor:
            where.append("actor_user_id=?")
            params.append(actor)
        if keyword:
            where.append("lower(action) LIKE ?")
            params.append(f"%{keyword}%")
        if category:
            where.append("lower(COALESCE(event_category, ''))=?")
            params.append(category)
        if sev:
            where.append("lower(COALESCE(severity, ''))=?")
            params.append(sev)
        if res:
            where.append("lower(result)=?")
            params.append(res)

        where_sql = f"WHERE {' AND '.join(where)}" if where else ""
        with self.conn_factory() as conn:
            rows = conn.execute(
                f"""
                SELECT event_id, actor_user_id, actor_role, action, event_category, severity,
                       resource_type, resource_id, result, ip, user_agent, detail, created_at,
                       prev_event_hash, event_hash, hash_kid
                FROM audit_logs
                {where_sql}
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (*params, cap),
            ).fetchall()
            return [dict(r) for r in rows]
