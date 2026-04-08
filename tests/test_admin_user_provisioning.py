import pytest
import hashlib

pytest.importorskip("fastapi")
from fastapi.testclient import TestClient

api_main = pytest.importorskip("app.api.main")


def test_admin_create_admin_requires_admin_role():
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = lambda: {
        "user_id": "u_view",
        "username": "viewer",
        "role": "viewer",
        "status": "active",
    }
    try:
        res = client.post(
            "/admin/users/create-admin",
            json={
                "username": "newadmin",
                "password": "Password123",
                "approval_token": "token",
                "ticket_id": "SEC-1",
                "reason": "need admin",
                "new_admin_approval_token": "new-admin-token-001",
            },
        )
        assert res.status_code == 403
    finally:
        api_main.app.dependency_overrides.clear()


def test_admin_create_admin_success(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = lambda: {
        "user_id": "u_admin",
        "username": "admin",
        "role": "admin",
        "status": "active",
    }
    monkeypatch.setattr(api_main.settings, "admin_create_approval_token", "approve-123")
    monkeypatch.setattr(
        api_main.auth_service,
        "create_user_with_role",
        lambda username, password, role="viewer", created_by_user_id=None, created_by_username=None, admin_ticket_id=None, admin_approval_token_hash=None: {
            "user_id": "u_new",
            "username": username,
            "role": role,
            "status": "active",
            "created_by_user_id": created_by_user_id,
            "created_by_username": created_by_username,
            "admin_ticket_id": admin_ticket_id,
            "has_admin_approval_token": True,
            "created_at": "2026-04-08T00:00:00+00:00",
        },
    )
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    try:
        res = client.post(
            "/admin/users/create-admin",
            json={
                "username": "newadmin",
                "password": "Password123",
                "approval_token": "approve-123",
                "ticket_id": "SEC-2026-001",
                "reason": "on-call admin rotation",
                "new_admin_approval_token": "new-admin-token-abc",
            },
        )
        assert res.status_code == 200
        data = res.json()
        assert data["role"] == "admin"
        assert data["username"] == "newadmin"
    finally:
        api_main.app.dependency_overrides.clear()


def test_admin_create_admin_rejects_invalid_approval_token(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = lambda: {
        "user_id": "u_admin",
        "username": "admin",
        "role": "admin",
        "status": "active",
    }
    monkeypatch.setattr(api_main.settings, "admin_create_approval_token", "approve-123")
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    try:
        res = client.post(
            "/admin/users/create-admin",
            json={
                "username": "newadmin",
                "password": "Password123",
                "approval_token": "bad",
                "ticket_id": "SEC-2026-002",
                "reason": "escalation",
                "new_admin_approval_token": "new-admin-token-def",
            },
        )
        assert res.status_code == 403
    finally:
        api_main.app.dependency_overrides.clear()


def test_admin_create_admin_uses_hash_token_when_configured(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = lambda: {
        "user_id": "u_admin",
        "username": "admin",
        "role": "admin",
        "status": "active",
    }
    # sha256("approve-123")
    monkeypatch.setattr(
        api_main.settings,
        "admin_create_approval_token_hash",
        "f3632fc7606f37418217d1d68fbe9590afd000f79ec5f594200b2d8fcb7f7648",
    )
    monkeypatch.setattr(api_main.settings, "admin_create_approval_token", "")
    monkeypatch.setattr(
        api_main.auth_service,
        "create_user_with_role",
        lambda username, password, role="viewer", created_by_user_id=None, created_by_username=None, admin_ticket_id=None, admin_approval_token_hash=None: {
            "user_id": "u_new2",
            "username": username,
            "role": role,
            "status": "active",
            "created_by_user_id": created_by_user_id,
            "created_by_username": created_by_username,
            "admin_ticket_id": admin_ticket_id,
            "has_admin_approval_token": True,
            "created_at": "2026-04-08T00:00:00+00:00",
        },
    )
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    try:
        res = client.post(
            "/admin/users/create-admin",
            json={
                "username": "newadmin2",
                "password": "Password123",
                "approval_token": "approve-123",
                "ticket_id": "SEC-2026-003",
                "reason": "hash mode validation",
                "new_admin_approval_token": "new-admin-token-ghi",
            },
        )
        assert res.status_code == 200
        assert res.json()["role"] == "admin"
    finally:
        api_main.app.dependency_overrides.clear()


def test_admin_update_role_blocks_promotion_to_admin():
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = lambda: {
        "user_id": "u_admin",
        "username": "admin",
        "role": "admin",
        "status": "active",
    }
    try:
        res = client.patch("/admin/users/u1/role", json={"role": "admin"})
        assert res.status_code == 400
        assert "restricted" in (res.json().get("detail", "") or "")
    finally:
        api_main.app.dependency_overrides.clear()


def test_admin_reset_approval_token_success(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = lambda: {
        "user_id": "u_admin",
        "username": "admin",
        "role": "admin",
        "status": "active",
    }

    monkeypatch.setattr(
        api_main.auth_service,
        "get_user_profile",
        lambda user_id: {
            "user_id": user_id,
            "username": "admin_target",
            "role": "admin",
            "status": "active",
            "admin_approval_token_hash": hashlib.sha256("my-own-token".encode("utf-8")).hexdigest(),
        }
        if user_id == "u_admin"
        else {
            "user_id": user_id,
            "username": "target",
            "role": "admin",
            "status": "active",
            "admin_approval_token_hash": "",
        },
    )
    monkeypatch.setattr(
        api_main.auth_service,
        "update_user_admin_approval_token",
        lambda user_id, admin_approval_token_hash, admin_ticket_id=None: {
            "user_id": user_id,
            "username": "target",
            "role": "admin",
            "status": "active",
            "created_by_user_id": "u_admin",
            "created_by_username": "admin",
            "admin_ticket_id": admin_ticket_id,
            "has_admin_approval_token": bool(admin_approval_token_hash),
            "created_at": "2026-04-08T00:00:00+00:00",
        },
    )
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    try:
        res = client.post(
            "/admin/users/u_target/reset-approval-token",
            json={
                "approval_token": "my-own-token",
                "ticket_id": "SEC-2026-010",
                "reason": "rotation due to role handoff",
                "new_admin_approval_token": "new-target-token-123",
            },
        )
        assert res.status_code == 200
        payload = res.json()
        assert payload["user_id"] == "u_target"
        assert payload["has_admin_approval_token"] is True
        assert payload["admin_ticket_id"] == "SEC-2026-010"
    finally:
        api_main.app.dependency_overrides.clear()


def test_admin_reset_approval_token_rejects_non_admin_target(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = lambda: {
        "user_id": "u_admin",
        "username": "admin",
        "role": "admin",
        "status": "active",
    }
    monkeypatch.setattr(
        api_main.auth_service,
        "get_user_profile",
        lambda user_id: {"user_id": user_id, "username": "viewer01", "role": "viewer", "status": "active"},
    )
    try:
        res = client.post(
            "/admin/users/u_view/reset-approval-token",
            json={
                "approval_token": "any-token",
                "ticket_id": "SEC-2026-011",
                "reason": "rotation",
                "new_admin_approval_token": "new-target-token-234",
            },
        )
        assert res.status_code == 400
    finally:
        api_main.app.dependency_overrides.clear()


def test_admin_reset_password_success(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = lambda: {
        "user_id": "u_admin",
        "username": "admin",
        "role": "admin",
        "status": "active",
    }

    monkeypatch.setattr(
        api_main.auth_service,
        "get_user_profile",
        lambda user_id: {
            "user_id": user_id,
            "username": "admin",
            "role": "admin",
            "status": "active",
            "admin_approval_token_hash": hashlib.sha256("my-own-token".encode("utf-8")).hexdigest(),
        }
        if user_id == "u_admin"
        else {
            "user_id": user_id,
            "username": "target_user",
            "role": "viewer",
            "status": "active",
            "admin_approval_token_hash": "",
        },
    )
    monkeypatch.setattr(
        api_main.auth_service,
        "update_user_password",
        lambda user_id, password: {
            "user_id": user_id,
            "username": "target_user",
            "role": "viewer",
            "status": "active",
            "created_by_user_id": "u_admin",
            "created_by_username": "admin",
            "admin_ticket_id": None,
            "has_admin_approval_token": False,
            "created_at": "2026-04-08T00:00:00+00:00",
        },
    )
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    try:
        res = client.post(
            "/admin/users/u_target/reset-password",
            json={
                "approval_token": "my-own-token",
                "ticket_id": "SEC-2026-020",
                "reason": "forgot password and account recovery",
                "new_password": "Password456",
            },
        )
        assert res.status_code == 200
        payload = res.json()
        assert payload["user_id"] == "u_target"
        assert payload["username"] == "target_user"
    finally:
        api_main.app.dependency_overrides.clear()


def test_admin_update_user_classification_success(monkeypatch):
    client = TestClient(api_main.app)
    api_main.app.dependency_overrides[api_main._require_user] = lambda: {
        "user_id": "u_admin",
        "username": "admin",
        "role": "admin",
        "status": "active",
    }
    monkeypatch.setattr(
        api_main.auth_service,
        "update_user_classification",
        lambda user_id, business_unit=None, department=None, user_type=None, data_scope=None: {
            "user_id": user_id,
            "username": "classified_user",
            "role": "viewer",
            "status": "active",
            "business_unit": business_unit,
            "department": department,
            "user_type": user_type,
            "data_scope": data_scope,
            "created_at": "2026-04-08T00:00:00+00:00",
        },
    )
    monkeypatch.setattr(api_main, "_audit", lambda *args, **kwargs: None)
    try:
        res = client.patch(
            "/admin/users/u_cls/classification",
            json={
                "business_unit": "Finance",
                "department": "Risk",
                "user_type": "employee",
                "data_scope": "P1",
            },
        )
        assert res.status_code == 200
        payload = res.json()
        assert payload["business_unit"] == "Finance"
        assert payload["department"] == "Risk"
        assert payload["user_type"] == "employee"
        assert payload["data_scope"] == "P1"
    finally:
        api_main.app.dependency_overrides.clear()
