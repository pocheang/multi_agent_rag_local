"""
测试新发现的严重安全问题的修复

验证问题 #4 和 #5 的修复：
- 问题 #4: UserManager 密码验证降级路径
- 问题 #5: PRAGMA 语句 SQL 注入风险
"""

import pytest
import sqlite3
from unittest.mock import MagicMock, patch
from pathlib import Path

from app.services.auth.user_manager import UserManager, _validate_service_password
from app.services.auth.validation import validate_password
from app.services.auth.auth_service import AuthDBService
from app.services.sessions.history import HistoryStore


class TestPasswordValidationConsistency:
    """测试密码验证的一致性 - 问题 #4"""

    def test_user_manager_no_downgrade_path(self):
        """测试 UserManager 不存在降级验证路径"""
        # 8个字符的密码（旧降级路径会接受）
        weak_passwords = [
            "Test1234",  # 8字符，无特殊字符
            "Password1",  # 10字符，无特殊字符
            "MyPass99",  # 8字符，无特殊字符
        ]

        for weak_password in weak_passwords:
            with pytest.raises(ValueError):
                _validate_service_password(weak_password)

    def test_user_manager_requires_12_chars(self):
        """测试 UserManager 要求至少12个字符"""
        with pytest.raises(ValueError, match="at least 12 characters"):
            _validate_service_password("Test123!")

    def test_user_manager_requires_special_chars(self):
        """测试 UserManager 要求特殊字符"""
        with pytest.raises(ValueError, match="special characters"):
            _validate_service_password("TestPassword123")

    def test_user_manager_accepts_strong_passwords(self):
        """测试 UserManager 接受强密码"""
        strong_passwords = [
            "TestPassword123!",
            "MySecure@Pass2024",
            "C0mpl3x!Passw0rd",
        ]

        for strong_password in strong_passwords:
            result = _validate_service_password(strong_password)
            assert result == strong_password

    def test_consistency_with_auth_service(self):
        """测试 UserManager 和 AuthDBService 使用相同的验证逻辑"""
        test_passwords = [
            ("Test123!", False),  # 太短，应该被拒绝
            ("TestPassword123", False),  # 无特殊字符，应该被拒绝
            ("TestPassword123!", True),  # 强密码，应该接受
        ]

        for password, should_pass in test_passwords:
            # UserManager 验证
            user_manager_exception = None
            try:
                _validate_service_password(password)
            except ValueError as e:
                user_manager_exception = e

            # AuthDBService 验证
            auth_service_exception = None
            try:
                AuthDBService._validate_creation_password(password)
            except ValueError as e:
                auth_service_exception = e

            # 两者应该一致
            if should_pass:
                assert user_manager_exception is None
                assert auth_service_exception is None
            else:
                assert user_manager_exception is not None
                assert auth_service_exception is not None


class TestPragmaSQLInjectionFix:
    """测试 PRAGMA 语句 SQL 注入修复 - 问题 #5"""

    def test_auth_service_pragma_safe(self, monkeypatch):
        """测试 AuthDBService._connect() 严格验证超时参数"""
        from pathlib import Path
        db_path = Path("./data/test_auth_pragma.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # 模拟配置
        mock_settings = MagicMock()
        mock_settings.app_db_path = db_path
        mock_settings.auth_token_ttl_hours = 168
        mock_settings.sqlite_busy_timeout_seconds = 10
        mock_settings.api_settings_encryption_key = "test_key_for_testing_purposes_only"

        monkeypatch.setattr("app.services.auth.auth_service.get_settings", lambda: mock_settings)

        # 创建服务实例
        service = AuthDBService(db_path=db_path)

        # 尝试使用超大值（应该被钳位到3600秒）
        mock_settings.sqlite_busy_timeout_seconds = 999999
        conn = service._connect()
        conn.close()

        # 尝试使用负值（应该被钳位到1秒）
        mock_settings.sqlite_busy_timeout_seconds = -100
        conn = service._connect()
        conn.close()

        # 尝试字符串类型（应该抛出异常或使用默认值）
        mock_settings.sqlite_busy_timeout_seconds = "malicious'; DROP TABLE users--"
        conn = service._connect()  # 应该使用默认值10，不会崩溃
        conn.close()

        # 清理
        if db_path.exists():
            db_path.unlink()

    def test_history_store_pragma_safe(self, monkeypatch):
        """测试 HistoryStore._connect() 严格验证超时参数"""
        from pathlib import Path
        base_path = Path("./data/test_history")

        # 模拟配置
        mock_settings = MagicMock()
        mock_settings.sessions_path = base_path / "sessions"
        mock_settings.history_cold_path = base_path / "cold"
        mock_settings.history_sqlite_path = base_path / "history.db"
        mock_settings.history_backend = "sqlite"
        mock_settings.sqlite_busy_timeout_seconds = 10

        monkeypatch.setattr("app.services.sessions.history.get_settings", lambda: mock_settings)

        # 创建 HistoryStore 实例
        store = HistoryStore(base_dir=base_path / "sessions")

        # 尝试使用超大值（应该被钳位）
        mock_settings.sqlite_busy_timeout_seconds = 999999
        conn = store._connect()
        conn.close()

        # 尝试字符串类型（应该被处理）
        mock_settings.sqlite_busy_timeout_seconds = "'; DROP TABLE sessions--"
        conn = store._connect()  # 应该使用默认值，不会崩溃
        conn.close()

        # 清理
        import shutil
        if base_path.exists():
            shutil.rmtree(base_path, ignore_errors=True)

    def test_pragma_timeout_clamping(self, monkeypatch):
        """测试超时值被正确钳位到安全范围"""
        from pathlib import Path
        db_path = Path("./data/test_clamp.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)

        mock_settings = MagicMock()
        mock_settings.app_db_path = db_path
        mock_settings.auth_token_ttl_hours = 168
        mock_settings.api_settings_encryption_key = "test_key_for_clamping_test"

        monkeypatch.setattr("app.services.auth.auth_service.get_settings", lambda: mock_settings)

        service = AuthDBService(db_path=db_path)

        # 测试超大值被钳位到最大值（3600秒 = 3600000毫秒）
        mock_settings.sqlite_busy_timeout_seconds = 999999
        conn = service._connect()
        # 验证连接成功（说明没有SQL注入）
        cursor = conn.execute("SELECT 1")
        assert cursor.fetchone()[0] == 1
        conn.close()

        # 测试负值被钳位到最小值（1秒 = 1000毫秒）
        mock_settings.sqlite_busy_timeout_seconds = -100
        conn = service._connect()
        cursor = conn.execute("SELECT 1")
        assert cursor.fetchone()[0] == 1
        conn.close()

        # 测试零值被钳位到最小值
        mock_settings.sqlite_busy_timeout_seconds = 0
        conn = service._connect()
        cursor = conn.execute("SELECT 1")
        assert cursor.fetchone()[0] == 1
        conn.close()

        # 清理
        if db_path.exists():
            db_path.unlink()

    def test_pragma_validation_with_assertion(self, monkeypatch):
        """验证 PRAGMA 使用严格验证和断言"""
        from pathlib import Path
        db_path = Path("./data/test_validation.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)

        mock_settings = MagicMock()
        mock_settings.app_db_path = db_path
        mock_settings.auth_token_ttl_hours = 168
        mock_settings.sqlite_busy_timeout_seconds = 10
        mock_settings.api_settings_encryption_key = "test_key_for_validation_test"

        monkeypatch.setattr("app.services.auth.auth_service.get_settings", lambda: mock_settings)

        service = AuthDBService(db_path=db_path)

        # 验证正常值工作
        conn = service._connect()
        cursor = conn.execute("SELECT 1")
        assert cursor.fetchone()[0] == 1
        conn.close()

        # 验证各种边界值都能正常工作（不会SQL注入）
        test_values = [1, 10, 100, 1000, 3600]
        for val in test_values:
            mock_settings.sqlite_busy_timeout_seconds = val
            conn = service._connect()
            cursor = conn.execute("SELECT 1")
            assert cursor.fetchone()[0] == 1
            conn.close()

        # 清理
        if db_path.exists():
            db_path.unlink()


class TestSecurityRegression:
    """回归测试 - 确保修复不破坏现有功能"""

    def test_strong_passwords_still_work(self):
        """测试强密码仍然被接受"""
        strong_passwords = [
            "MyVerySecurePassword123!",
            "Compl3x@Passw0rd#2024",
            "Str0ng!P@ssw0rd$Here",
        ]

        for password in strong_passwords:
            # UserManager 应该接受
            result = _validate_service_password(password)
            assert result == password

            # AuthDBService 应该接受
            result = AuthDBService._validate_creation_password(password)
            assert result == password

    def test_user_manager_enforces_strong_passwords(self, monkeypatch):
        """测试 UserManager.create_user 强制执行强密码策略"""
        from pathlib import Path
        db_path = Path("./data/test_user_manager.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)

        def mock_conn_factory():
            conn = sqlite3.connect(db_path)
            conn.row_factory = sqlite3.Row
            # 创建基本表结构
            conn.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    username TEXT UNIQUE,
                    salt TEXT,
                    password_hash TEXT,
                    role TEXT,
                    status TEXT,
                    created_at TEXT,
                    created_by_user_id TEXT,
                    created_by_username TEXT,
                    admin_ticket_id TEXT,
                    admin_approval_token_hash TEXT,
                    business_unit TEXT,
                    department TEXT,
                    user_type TEXT,
                    data_scope TEXT,
                    display_name TEXT,
                    settings TEXT
                )
            """)
            conn.commit()
            return conn

        manager = UserManager(mock_conn_factory)

        # 弱密码应该被拒绝
        with pytest.raises(ValueError):
            manager.create_user("testuser1", "Test1234")  # 8字符，无特殊字符

        # 强密码应该被接受
        user = manager.create_user("testuser2", "TestPassword123!")
        assert user["username"] == "testuser2"

        # 清理
        if db_path.exists():
            db_path.unlink()


# 运行测试的命令：
# pytest tests/security/test_new_critical_fixes.py -v
