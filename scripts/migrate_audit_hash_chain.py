from __future__ import annotations

import json
import sqlite3

from app.core.config import get_settings
from app.services.alerting import resolve_signing_secret, sign_payload


def main():
    settings = get_settings()
    db = settings.app_db_path
    kid, secret = resolve_signing_secret()
    if not secret:
        raise SystemExit("missing signing secret: set RESPONSE_SIGNING_KEYS or RESPONSE_SIGNING_SECRET")
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(audit_logs)")
    cols = {str(r[1]) for r in cur.fetchall()}
    if "prev_event_hash" not in cols:
        cur.execute("ALTER TABLE audit_logs ADD COLUMN prev_event_hash TEXT")
    if "event_hash" not in cols:
        cur.execute("ALTER TABLE audit_logs ADD COLUMN event_hash TEXT")
    if "hash_kid" not in cols:
        cur.execute("ALTER TABLE audit_logs ADD COLUMN hash_kid TEXT")

    rows = conn.execute(
        "SELECT * FROM audit_logs ORDER BY created_at ASC, event_id ASC"
    ).fetchall()
    prev_hash = None
    updated = 0
    for r in rows:
        payload = {
            "event_id": str(r["event_id"] or ""),
            "created_at": str(r["created_at"] or ""),
            "prev_event_hash": prev_hash or "",
            "actor_user_id": str(r["actor_user_id"] or ""),
            "actor_role": str(r["actor_role"] or ""),
            "action": str(r["action"] or ""),
            "event_category": str(r["event_category"] or ""),
            "severity": str(r["severity"] or ""),
            "resource_type": str(r["resource_type"] or ""),
            "resource_id": str(r["resource_id"] or ""),
            "result": str(r["result"] or ""),
            "ip": str(r["ip"] or ""),
            "user_agent": str(r["user_agent"] or ""),
            "detail": str(r["detail"] or ""),
        }
        ev_hash = sign_payload(payload, secret)
        conn.execute(
            "UPDATE audit_logs SET prev_event_hash=?, event_hash=?, hash_kid=? WHERE event_id=?",
            (prev_hash, ev_hash, kid, str(r["event_id"])),
        )
        prev_hash = ev_hash
        updated += 1
    conn.commit()
    conn.close()
    print(json.dumps({"ok": True, "updated": updated, "hash_kid": kid}, ensure_ascii=False))


if __name__ == "__main__":
    main()
