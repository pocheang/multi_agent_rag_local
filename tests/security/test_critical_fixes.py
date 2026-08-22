"""
测试关键安全修复

验证立即修复的3个严重安全问题：
1. SQL注入风险修复
2. 密码策略统一
3. 加密密钥配置
"""

import pytest
import secrets
from unittest.mock import MagicMock, AsyncMock

from app.database.query_optimizer import QueryOptimizer, _validated_identifier, ALLOWED_TABLES
from app.services.auth.auth_service import AuthDBService
from app.services.auth.validation import validate_password


class TestSQLInjectionFixes:
    """测试SQL注入修复"""

    def test_validated_identifier_whitelist(self):
        """测试白名单验证"""
        # 合法的表名应该通过
        for table in ALLOWED_TABLES:
            assert _validated_identifier(table) == table

        # 不在白名单中的表名应该被拒绝
        with pytest.raises(ValueError, match="not in whitelist"):
            _validated_identifier("malicious_table")

    def test_validated_identifier_sql_injection(self):
        """测试SQL注入攻击被阻止"""
        # 尝试注入恶意SQL
        malicious_inputs = [
            "users; DROP TABLE users--",
            "users' OR '1'='1",
            "users/**/UNION/**/SELECT/**/*",
            "users`; DELETE FROM users WHERE `1`=`1",
            "../../../etc/passwd",
            "users\x00admin",
        ]

        for malicious in malicious_inputs:
            with pytest.raises(ValueError):
                _validated_identifier(malicious)

    def test_validated_identifier_length_limit(self):
        """测试标识符长度限制"""
        # 空字符串
        with pytest.raises(ValueError, match="Invalid SQL identifier length"):
            _validated_identifier("")

        # 超长标识符
        with pytest.raises(ValueError, match="Invalid SQL identifier length"):
            _validated_identifier("a" * 65)

    def test_validated_identifier_format(self):
        """测试标识符格式验证"""
        # 必须以字母或下划线开头
        with pytest.raises(ValueError, match="Invalid SQL identifier format"):
            _validated_identifier("123users")

        # 不能包含特殊字符
        with pytest.raises(ValueError, match="Invalid SQL identifier format"):
            _validated_identifier("users-table")

    @pytest.mark.asyncio
    async def test_explain_query_disabled(self):
        """测试 explain_query 功能已被禁用"""
        session = MagicMock()
        optimizer = QueryOptimizer()

        with pytest.raises(NotImplementedError, match="disabled for security"):
            await optimizer.explain_query(session, "SELECT * FROM users")


class TestPasswordPolicyConsistency:
    """测试密码策略一致性"""

    def test_validate_creation_password_requires_12_chars(self):
        """测试密码必须至少12个字符"""
        # 8个字符的密码应该被拒绝（即使符合其他要求）
        with pytest.raises(ValueError, match="at least 12 characters"):
            AuthDBService._validate_creation_password("Test123!")

    def test_validate_creation_password_requires_special_chars(self):
        """测试密码必须包含特殊字符"""
        # 没有特殊字符的密码应该被拒绝
        with pytest.raises(ValueError, match="special characters"):
            AuthDBService._validate_creation_password("TestPassword123")

    def test_validate_creation_password_no_downgrade(self):
        """测试不存在降级验证路径"""
        # 曾经的降级路径（8个字符，无特殊字符）现在应该被拒绝
        weak_passwords = [
            "Test1234",  # 8个字符，无特殊字符
            "TestTest1",  # 9个字符，无特殊字符
            "Password1",  # 10个字符，无特殊字符
        ]

        for weak_password in weak_passwords:
            with pytest.raises(ValueError):
                AuthDBService._validate_creation_password(weak_password)

    def test_validate_creation_password_strong_accepted(self):
        """测试强密码被接受"""
        strong_passwords = [
            "TestPassword123!",  # 符合所有要求
            "MySecure@Pass2024",  # 符合所有要求
            "C0mpl3x!Passw0rd",  # 符合所有要求
        ]

        for strong_password in strong_passwords:
            result = AuthDBService._validate_creation_password(strong_password)
            assert result == strong_password

    def test_oauth_users_follow_same_policy(self):
        """测试OAuth用户遵循相同的密码策略"""
        # OAuth用户创建时生成的密码应该符合标准策略
        # 格式：GoogleOAuth1!{32-char-token}
        oauth_password = f"GoogleOAuth1!{secrets.token_urlsafe(32)}"

        # 应该通过验证
        result = AuthDBService._validate_creation_password(oauth_password)
        assert result == oauth_password

        # 验证它确实符合所有要求
        assert len(result) >= 12
        assert any(c.islower() for c in result)
        assert any(c.isupper() for c in result)
        assert any(c.isdigit() for c in result)
        assert any(c in "!@#$%^&*()_+-=[]{}|;:,.<>?" for c in result)


class TestEncryptionKeyConfiguration:
    """测试加密密钥配置"""

    def test_encryption_key_required(self, monkeypatch):
        """测试加密密钥是必需的"""
        from pathlib import Path
        from unittest.mock import MagicMock

        # 模拟缺失加密密钥的情况
        mock_settings = MagicMock()
        mock_settings.app_db_path = Path("./data/test_auth.db")
        mock_settings.auth_token_ttl_hours = 168
        # 明确设置为空字符串（模拟缺失）
        mock_settings.api_settings_encryption_key = ""

        monkeypatch.setattr("app.services.auth.auth_service.get_settings", lambda: mock_settings)

        # 尝试创建服务实例
        service = AuthDBService()

        # 尝试访问加密密钥应该抛出异常
        with pytest.raises(RuntimeError, match="API_SETTINGS_ENCRYPTION_KEY.*required"):
            service._api_settings_data_key()

    def test_env_example_has_encryption_key_docs(self):
        """测试 .env.example 包含加密密钥文档"""
        import os
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        env_example_path = os.path.join(project_root, ".env.example")

        with open(env_example_path, "r", encoding="utf-8") as f:
            content = f.read()

        # 验证包含加密密钥配置
        assert "API_SETTINGS_ENCRYPTION_KEY" in content
        assert "secrets.token_urlsafe(48)" in content
        assert "用于加密存储" in content or "API KEY ENCRYPTION" in content.upper()

        # 验证包含警告信息
        assert "警告" in content or "WARNING" in content.upper()
        """测试 .env.example 包含加密密钥文档"""
        with open(".env.example", "r", encoding="utf-8") as f:
            content = f.read()

        # 验证包含加密密钥配置
        assert "API_SETTINGS_ENCRYPTION_KEY" in content
        assert "secrets.token_urlsafe(48)" in content
        assert "用于加密存储" in content or "API KEY ENCRYPTION" in content

        # 验证包含警告信息
        assert "警告" in content or "WARNING" in content.upper()


class TestSecurityRegression:
    """回归测试 - 确保修复不会破坏现有功能"""

    @pytest.mark.asyncio
    async def test_legitimate_table_operations_still_work(self):
        """测试合法的表操作仍然可用"""
        session = AsyncMock()
        optimizer = QueryOptimizer()

        # 模拟成功的数据库操作
        session.execute = AsyncMock()

        # 对白名单中的表执行操作应该成功
        for table in ["users", "auth_sessions", "audit_logs"]:
            await optimizer.analyze_table(session, table)
            session.execute.assert_called()

    def test_strong_passwords_still_accepted(self):
        """测试强密码仍然被接受"""
        strong_passwords = [
            "MyVerySecurePassword123!",
            "Compl3x@Passw0rd#2024",
            "Str0ng!P@ssw0rd$Here",
        ]

        for password in strong_passwords:
            # 不应该抛出异常
            result = validate_password(password)
            assert result == password


# 运行测试的命令：
# pytest tests/security/test_critical_fixes.py -v
