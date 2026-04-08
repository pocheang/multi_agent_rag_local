from app.services.rbac import can


def test_admin_has_all_permissions():
    user = {"role": "admin"}
    assert can("admin:user_manage", user) is True
    assert can("upload:create", user) is True
    assert can("query:run", user) is True


def test_analyst_permissions():
    user = {"role": "analyst"}
    assert can("query:run", user) is True
    assert can("upload:create", user) is True
    assert can("document:manage_own", user) is True
    assert can("admin:user_manage", user) is False
    assert can("admin:audit_read", user) is False


def test_viewer_permissions():
    user = {"role": "viewer"}
    assert can("query:run", user) is True
    assert can("prompt:manage", user) is True
    assert can("document:read", user) is True
    assert can("upload:create", user) is True
    assert can("document:manage_own", user) is True
    assert can("admin:user_manage", user) is False


def test_unknown_role_defaults_to_deny():
    user = {"role": "unknown"}
    assert can("query:run", user) is False
