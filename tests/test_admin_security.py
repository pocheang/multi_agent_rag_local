"""管理员安全测试

测试管理员操作的安全漏洞修复。
"""
import pytest
from unittest import mock
from fastapi.testclient import TestClient


class TestAdminSelfModification:
    """测试自我修改防护"""

    def test_admin_cannot_modify_own_role(self, client, admin_headers, admin_user_id):
        """严重: 防止自我权限提升"""
        response = client.patch(
            f"/admin/users/{admin_user_id}/role",
            json={"role": "super_admin"},
            headers=admin_headers
        )
        assert response.status_code == 403
        assert "cannot modify your own" in response.json()["detail"].lower()

    def test_admin_cannot_disable_self(self, client, admin_headers, admin_user_id):
        """严重: 防止自我禁用"""
        response = client.patch(
            f"/admin/users/{admin_user_id}/status",
            json={"status": "disabled"},
            headers=admin_headers
        )
        assert response.status_code == 403
        assert "cannot modify your own" in response.json()["detail"].lower()

    def test_admin_cannot_reset_own_approval_token(self, client, admin_headers, admin_user_id):
        """严重: 防止自我重置审批令牌"""
        response = client.post(
            f"/admin/users/{admin_user_id}/reset-approval-token",
            json={
                "approval_token": "valid-token",
                "ticket_id": "JIRA-123",
                "reason": "test reason",
                "new_admin_approval_token": "new-token-123456"
            },
            headers=admin_headers
        )
        assert response.status_code == 403


class TestApprovalTokenSecurity:
    """测试审批令牌安全"""

    def test_approval_token_single_use(self, client, admin_headers):
        """严重: 防止令牌重复使用"""
        token = "test-approval-token-12345678"

        # 第一次使用成功
        response1 = client.post("/admin/users/create-admin", json={
            "username": "testadmin1",
            "password": "SecurePass123!",
            "approval_token": token,
            "ticket_id": "JIRA-123",
            "reason": "legitimate business need",
            "new_admin_approval_token": "new-token-1234567890"
        }, headers=admin_headers)

        # 第二次使用同一令牌失败
        response2 = client.post("/admin/users/create-admin", json={
            "username": "testadmin2",
            "password": "SecurePass123!",
            "approval_token": token,  # 重复使用
            "ticket_id": "JIRA-124",
            "reason": "another reason",
            "new_admin_approval_token": "new-token-0987654321"
        }, headers=admin_headers)

        # 至少有一个应该失败
        assert response1.status_code == 200 or response2.status_code == 403
        if response1.status_code == 200:
            assert response2.status_code == 403

    def test_approval_token_error_message_no_leak(self, client, admin_headers):
        """高危: 防止信息泄露"""
        # 使用无效令牌
        response = client.post("/admin/users/create-admin", json={
            "username": "testadmin",
            "password": "SecurePass123!",
            "approval_token": "invalid-token",
            "ticket_id": "JIRA-123",
            "reason": "test reason",
            "new_admin_approval_token": "new-token-123456"
        }, headers=admin_headers)

        assert response.status_code == 403
        # 错误消息应该是通用的，不泄露配置信息
        detail = response.json()["detail"].lower()
        assert "unauthorized" in detail or "invalid" in detail
        assert "missing" not in detail  # 不应泄露配置状态
        assert "configured" not in detail


class TestUserStatusEnforcement:
    """测试用户状态强制执行"""

    def test_disabled_admin_cannot_act(self, client, auth_service, admin_user_id, admin_token):
        """严重: 强制状态检查"""
        # 禁用管理员
        auth_service.update_user_status(admin_user_id, "disabled")

        # 尝试管理员操作
        response = client.get(
            "/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"}
        )

        assert response.status_code == 403
        assert "not active" in response.json()["detail"].lower()

    def test_suspended_user_cannot_login(self, client, auth_service):
        """中危: 暂停用户无法登录"""
        # 创建并暂停用户
        user = auth_service.register("suspended_user", "Password123!")
        auth_service.update_user_status(user["user_id"], "suspended")

        # 尝试登录
        response = client.post("/auth/login", json={
            "username": "suspended_user",
            "password": "Password123!"
        })

        # 应该失败或返回403
        assert response.status_code in [401, 403]


class TestRateLimiting:
    """测试速率限制"""

    def test_rate_limiting_on_admin_creation(self, client, admin_headers):
        """中危: 防止暴力破解"""
        # 快速连续创建多个管理员
        responses = []
        for i in range(3):
            response = client.post("/admin/users/create-admin", json={
                "username": f"admin{i}",
                "password": "SecurePass123!",
                "approval_token": f"token-{i}-123456789",
                "ticket_id": f"JIRA-{i}",
                "reason": "test reason for rate limit",
                "new_admin_approval_token": f"new-token-{i}-123456789"
            }, headers=admin_headers)
            responses.append(response)

        # 至少有一个应该被速率限制阻止
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes or 403 in status_codes

    def test_rate_limiting_on_password_reset(self, client, admin_headers, test_user_id):
        """中危: 密码重置速率限制"""
        # 快速连续重置密码
        responses = []
        for i in range(7):
            response = client.post(
                f"/admin/users/{test_user_id}/reset-password",
                json={
                    "approval_token": f"token-{i}",
                    "ticket_id": f"JIRA-{i}",
                    "reason": "test reason",
                    "new_password": f"NewPass{i}!"
                },
                headers=admin_headers
            )
            responses.append(response)

        # 应该有速率限制
        status_codes = [r.status_code for r in responses]
        assert 429 in status_codes


class TestAuditLogging:
    """测试审计日志"""

    def test_audit_log_on_exception(self, client, admin_headers, auth_service):
        """高危: 确保所有失败都被审计"""
        user_id = "test-user-123"

        # 触发异常
        with mock.patch.object(
            auth_service,
            'update_user_role',
            side_effect=Exception("database error")
        ):
            response = client.patch(
                f"/admin/users/{user_id}/role",
                json={"role": "analyst"},
                headers=admin_headers
            )

        # 检查审计日志
        logs = auth_service.list_audit_logs(
            action_keyword="role_update",
            result="failed"
        )
        assert len(logs) > 0
        # 应该记录异常类型
        assert any("Exception" in log.get("detail", "") for log in logs)

    def test_audit_log_on_self_modification_attempt(self, client, admin_headers, admin_user_id, auth_service):
        """高危: 自我修改尝试应被审计"""
        # 尝试自我修改
        client.patch(
            f"/admin/users/{admin_user_id}/role",
            json={"role": "viewer"},
            headers=admin_headers
        )

        # 检查审计日志
        logs = auth_service.list_audit_logs(
            action_keyword="role_update",
            result="blocked_self_modification"
        )
        assert len(logs) > 0


class TestInputValidation:
    """测试输入验证"""

    def test_ticket_id_format_validation(self, client, admin_headers):
        """中危: 验证工单 ID 格式"""
        response = client.post("/admin/users/create-admin", json={
            "username": "testadmin",
            "password": "SecurePass123!",
            "approval_token": "valid-token-123456",
            "ticket_id": "invalid",  # 无效格式
            "reason": "test reason",
            "new_admin_approval_token": "new-token-123456"
        }, headers=admin_headers)

        assert response.status_code == 400
        assert "invalid ticket format" in response.json()["detail"].lower()

    def test_reason_length_validation(self, client, admin_headers):
        """中危: 验证原因长度"""
        response = client.post("/admin/users/create-admin", json={
            "username": "testadmin",
            "password": "SecurePass123!",
            "approval_token": "valid-token-123456",
            "ticket_id": "JIRA-123",
            "reason": "ab",  # 太短
            "new_admin_approval_token": "new-token-123456"
        }, headers=admin_headers)

        assert response.status_code == 400
        assert "reason" in response.json()["detail"].lower()

    def test_approval_token_length_validation(self, client, admin_headers):
        """中危: 验证审批令牌长度"""
        response = client.post("/admin/users/create-admin", json={
            "username": "testadmin",
            "password": "SecurePass123!",
            "approval_token": "valid-token-123456",
            "ticket_id": "JIRA-123",
            "reason": "test reason",
            "new_admin_approval_token": "short"  # 太短
        }, headers=admin_headers)

        assert response.status_code == 400
        assert "approval token" in response.json()["detail"].lower()


# Fixtures

@pytest.fixture
def admin_user_id(auth_service):
    """创建测试管理员用户"""
    import uuid
    username = f"test_admin_{uuid.uuid4().hex[:8]}"
    user = auth_service.create_user_with_role(
        username=username,
        password="AdminPass123!",
        role="admin"
    )
    yield user["user_id"]
    # Cleanup
    try:
        auth_service.user_manager.delete_user(user["user_id"])
    except:
        pass


@pytest.fixture
def admin_token(auth_service, admin_user_id):
    """获取管理员令牌"""
    # Get username from user_id
    user = auth_service.user_manager.get_user_profile(admin_user_id)
    result = auth_service.login(user["username"], "AdminPass123!")
    return result["token"]


@pytest.fixture
def admin_headers(admin_token):
    """管理员请求头"""
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture
def test_user_id(auth_service):
    """创建测试普通用户"""
    import uuid
    username = f"test_user_{uuid.uuid4().hex[:8]}"
    user = auth_service.register(username, "UserPass123!")
    yield user["user_id"]
    # Cleanup
    try:
        auth_service.user_manager.delete_user(user["user_id"])
    except:
        pass
