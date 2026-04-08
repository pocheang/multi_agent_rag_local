import uuid
import hashlib
from pathlib import Path

import pytest

from app.services.auth_db import AuthDBService


def _mk(prefix: str) -> Path:
    path = Path("tests/.tmp") / f"{prefix}-{uuid.uuid4().hex[:8]}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_auth_db_register_login_and_token_lookup():
    root = _mk("auth-db")
    service = AuthDBService(db_path=root / "app.db", token_ttl_hours=1)
    user = service.register("dbuser01", "Password123")
    assert user["username"] == "dbuser01"

    login = service.login("dbuser01", "Password123")
    me = service.get_user_by_token(login["token"])
    assert me is not None
    assert me["username"] == "dbuser01"
    assert me["role"] == "viewer"
    assert me["status"] == "active"


def test_auth_db_duplicate_username():
    root = _mk("auth-db-dupe")
    service = AuthDBService(db_path=root / "app.db", token_ttl_hours=1)
    service.register("dup01", "Password123")
    with pytest.raises(ValueError):
        service.register("dup01", "Password123")


def test_auth_db_disable_user_blocks_login_and_token():
    root = _mk("auth-db-disable")
    service = AuthDBService(db_path=root / "app.db", token_ttl_hours=1)
    user = service.register("disable01", "Password123")
    login = service.login("disable01", "Password123")
    assert service.get_user_by_token(login["token"]) is not None

    updated = service.update_user_status(user["user_id"], "disabled")
    assert updated is not None
    assert updated["status"] == "disabled"
    assert service.get_user_by_token(login["token"]) is None

    with pytest.raises(ValueError):
        service.login("disable01", "Password123")


def test_auth_db_role_and_audit_log_flow():
    root = _mk("auth-db-admin")
    service = AuthDBService(db_path=root / "app.db", token_ttl_hours=1)
    user = service.register("role01", "Password123")

    row = service.update_user_role(user["user_id"], "analyst")
    assert row is not None
    assert row["role"] == "analyst"

    event = service.add_audit_log(
        action="admin.user.role_update",
        resource_type="user",
        result="success",
        actor_user_id=user["user_id"],
        actor_role="admin",
        resource_id=user["user_id"],
        detail="role=analyst",
    )
    assert event["event_id"]

    logs = service.list_audit_logs(limit=5)
    assert len(logs) >= 1
    assert logs[0]["action"] == "admin.user.role_update"


def test_auth_db_update_user_admin_approval_token():
    root = _mk("auth-db-admin-token")
    service = AuthDBService(db_path=root / "app.db", token_ttl_hours=1)
    user = service.create_user_with_role("admintoken01", "Password123", role="admin")
    digest = hashlib.sha256("my-new-token-123".encode("utf-8")).hexdigest()

    updated = service.update_user_admin_approval_token(
        user_id=user["user_id"],
        admin_approval_token_hash=digest,
        admin_ticket_id="SEC-2026-012",
    )
    assert updated is not None
    assert int(updated["has_admin_approval_token"]) == 1
    assert updated["admin_ticket_id"] == "SEC-2026-012"


def test_auth_db_classification_and_audit_filter():
    root = _mk("auth-db-class")
    service = AuthDBService(db_path=root / "app.db", token_ttl_hours=1)
    user = service.create_user_with_role("classuser01", "Password123", role="viewer")
    updated = service.update_user_classification(
        user_id=user["user_id"],
        business_unit="Finance",
        department="Risk",
        user_type="employee",
        data_scope="P1",
    )
    assert updated is not None
    assert updated["business_unit"] == "Finance"
    assert updated["department"] == "Risk"
    service.add_audit_log(
        action="admin.user.classification_update",
        resource_type="user",
        result="success",
        actor_user_id="admin1",
        actor_role="admin",
        resource_id=user["user_id"],
    )
    rows = service.list_audit_logs(limit=20, event_category="admin", severity="info")
    assert len(rows) >= 1
    assert rows[0]["event_category"] == "admin"


def test_auth_db_online_10m_flag_and_touch_session():
    root = _mk("auth-db-online")
    service = AuthDBService(db_path=root / "app.db", token_ttl_hours=1)
    service.register("online01", "Password123")
    login = service.login("online01", "Password123")
    token = login["token"]

    rows = service.list_users()
    row = next(x for x in rows if x["username"] == "online01")
    assert int(row["is_online"]) == 1
    assert int(row["is_online_10m"]) == 1

    # simulate stale last_seen_at
    with service._connect() as conn:
        conn.execute(
            "UPDATE auth_sessions SET last_seen_at=datetime('now','-20 minutes') WHERE token=?",
            (token,),
        )
    rows2 = service.list_users()
    row2 = next(x for x in rows2 if x["username"] == "online01")
    assert int(row2["is_online"]) == 1
    assert int(row2["is_online_10m"]) == 0

    service.touch_session(token)
    rows3 = service.list_users()
    row3 = next(x for x in rows3 if x["username"] == "online01")
    assert int(row3["is_online_10m"]) == 1


def test_auth_db_update_user_password_forces_relogin():
    root = _mk("auth-db-reset-pwd")
    service = AuthDBService(db_path=root / "app.db", token_ttl_hours=1)
    user = service.register("resetpwd01", "Password123")
    login = service.login("resetpwd01", "Password123")
    assert service.get_user_by_token(login["token"]) is not None

    updated = service.update_user_password(user["user_id"], "Password456")
    assert updated is not None
    assert updated["user_id"] == user["user_id"]
    # Existing sessions should be invalidated after password reset.
    assert service.get_user_by_token(login["token"]) is None

    with pytest.raises(ValueError):
        service.login("resetpwd01", "Password123")
    new_login = service.login("resetpwd01", "Password456")
    assert new_login["user"]["username"] == "resetpwd01"
