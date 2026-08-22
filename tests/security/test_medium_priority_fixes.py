"""
测试中等优先级安全问题的修复

验证问题 #7-10 的修复：
- 问题 #7: 数据库索引优化
- 问题 #8: 会话管理并发控制
- 问题 #9: 审计日志完整性保护
- 问题 #10: LRU缓存驱逐策略
"""

import pytest
import sqlite3
import threading
import time
from pathlib import Path
from unittest.mock import patch
from datetime import datetime, UTC

from app.services.sessions.metadata_db import SessionMetadataDB, SessionMetadata
from app.services.auth.auth_service import AuthDBService


class TestDatabaseIndexOptimization:
    """测试数据库索引优化 - 问题 #7"""

    def test_composite_indexes_created(self, monkeypatch):
        """测试复合索引被正确创建"""
        db_path = Path("./data/test_indexes.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # 清理旧数据库
        if db_path.exists():
            db_path.unlink()

        # 创建数据库实例
        db = SessionMetadataDB(db_path=db_path)

        # 验证索引是否存在
        with db._connect() as conn:
            indexes = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='session_metadata'"
            ).fetchall()
            index_names = {row[0] for row in indexes}

            # 验证基本索引
            assert "idx_session_updated_at" in index_names
            assert "idx_session_category" in index_names

            # 验证新添加的复合索引
            assert "idx_session_category_updated" in index_names
            assert "idx_session_last_query" in index_names

        # 清理
        if db_path.exists():
            db_path.unlink()


class TestConcurrencyControl:
    """测试会话管理并发控制 - 问题 #8"""

    def test_concurrent_create_prevents_race_condition(self, monkeypatch):
        """测试并发创建会话时防止竞态条件"""
        db_path = Path("./data/test_concurrency.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # 清理旧数据库
        if db_path.exists():
            db_path.unlink()

        db = SessionMetadataDB(db_path=db_path)

        session_id = "test_concurrent_session"
        metadata = SessionMetadata(
            session_id=session_id,
            tags=["test"],
            category="general",
            description="Test session",
        )

        results = []
        errors = []

        def create_session():
            try:
                db.create(metadata)
                results.append("success")
            except ValueError as e:
                errors.append(str(e))
            except Exception as e:
                errors.append(f"unexpected: {e}")

        # 启动多个线程尝试同时创建相同的会话
        threads = []
        for i in range(5):
            t = threading.Thread(target=create_session)
            threads.append(t)
            t.start()

        # 等待所有线程完成
        for t in threads:
            t.join()

        # 验证：只有一个成功，其余都失败
        assert len(results) == 1, f"Expected 1 success, got {len(results)}"
        assert len(errors) == 4, f"Expected 4 errors, got {len(errors)}"

        # 验证错误消息
        for error in errors:
            assert "already exists" in error

        # 清理
        if db_path.exists():
            db_path.unlink()


class TestAuditLogImmutability:
    """测试审计日志完整性保护 - 问题 #9"""

    def test_audit_logs_cannot_be_updated(self, monkeypatch):
        """测试审计日志不能被修改"""
        db_path = Path("./data/test_audit_immutable.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # 清理旧数据库
        if db_path.exists():
            db_path.unlink()

        mock_settings = MagicMock()
        mock_settings.app_db_path = db_path
        mock_settings.auth_token_ttl_hours = 168
        mock_settings.api_settings_encryption_key = "test_key_audit_immutable"

        monkeypatch.setattr("app.services.auth.auth_service.get_settings", lambda: mock_settings)

        # 创建服务实例
        service = AuthDBService(db_path=db_path)

        # 创建一条审计日志
        with service._connect() as conn:
            event_id = "test_event_001"
            conn.execute(
                """
                INSERT INTO audit_logs (event_id, action, resource_type, result, created_at)
                VALUES (?, 'test_action', 'test_resource', 'success', ?)
                """,
                (event_id, datetime.now(UTC).isoformat())
            )
            conn.commit()

        # 尝试修改审计日志 - 应该失败
        with service._connect() as conn:
            with pytest.raises(sqlite3.IntegrityError, match="Audit logs are immutable"):
                conn.execute(
                    "UPDATE audit_logs SET action = 'modified_action' WHERE event_id = ?",
                    (event_id,)
                )

        # 尝试删除审计日志 - 应该失败
        with service._connect() as conn:
            with pytest.raises(sqlite3.IntegrityError, match="cannot be deleted"):
                conn.execute("DELETE FROM audit_logs WHERE event_id = ?", (event_id,))

        # 验证日志仍然存在且未被修改
        with service._connect() as conn:
            row = conn.execute(
                "SELECT action FROM audit_logs WHERE event_id = ?",
                (event_id,)
            ).fetchone()
            assert row is not None
            assert row[0] == "test_action"

        # 清理
        if db_path.exists():
            db_path.unlink()


class TestLRUCacheLogging:
    """测试LRU缓存驱逐策略 - 问题 #10"""

    def test_cache_eviction_uses_logger(self, monkeypatch, caplog):
        """测试缓存驱逐使用logger而非print"""
        import logging
        caplog.set_level(logging.DEBUG)

        db_path = Path("./data/test_cache_logging.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # 清理旧数据库
        if db_path.exists():
            db_path.unlink()

        # 创建小缓存的数据库实例
        db = SessionMetadataDB(db_path=db_path, max_cache_size=3)

        # 创建多个会话以触发缓存驱逐
        for i in range(5):
            metadata = SessionMetadata(
                session_id=f"session_{i}",
                tags=["test"],
                category="general",
                description=f"Session {i}",
            )
            db.create(metadata)

        # 验证日志中有驱逐记录
        assert any("evicted" in record.message.lower() for record in caplog.records)
        assert any("session" in record.message.lower() for record in caplog.records)

        # 验证使用的是logger而非print（通过检查日志级别）
        eviction_logs = [r for r in caplog.records if "evicted" in r.message.lower()]
        for log in eviction_logs:
            assert log.levelname == "DEBUG"

        # 清理
        if db_path.exists():
            db_path.unlink()

    def test_cache_stats_available(self):
        """测试缓存统计信息可用"""
        db_path = Path("./data/test_cache_stats.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # 清理旧数据库
        if db_path.exists():
            db_path.unlink()

        db = SessionMetadataDB(db_path=db_path)

        # 获取统计信息
        stats = db.get_stats()

        # 验证统计信息包含必要字段
        assert "total_in_db" in stats
        assert "total_in_cache" in stats
        assert "max_cache_size" in stats
        assert "cache_hit_rate" in stats

        # 清理
        if db_path.exists():
            db_path.unlink()


class TestSecurityRegression:
    """回归测试 - 确保修复不破坏现有功能"""

    def test_normal_session_operations_still_work(self):
        """测试正常的会话操作仍然工作"""
        db_path = Path("./data/test_regression.db")
        db_path.parent.mkdir(parents=True, exist_ok=True)

        # 清理旧数据库
        if db_path.exists():
            db_path.unlink()

        db = SessionMetadataDB(db_path=db_path)

        # 创建会话
        metadata = SessionMetadata(
            session_id="test_session",
            tags=["test", "regression"],
            category="general",
            description="Test session for regression",
        )
        created = db.create(metadata)
        assert created.session_id == "test_session"

        # 读取会话
        retrieved = db.get("test_session")
        assert retrieved is not None
        assert retrieved.session_id == "test_session"
        assert "test" in retrieved.tags

        # 更新会话
        retrieved.description = "Updated description"
        db.update(retrieved)

        # 验证更新
        updated = db.get("test_session")
        assert updated.description == "Updated description"

        # 删除会话
        result = db.delete("test_session")
        assert result is True

        # 验证删除
        deleted = db.get("test_session")
        assert deleted is None

        # 清理
        if db_path.exists():
            db_path.unlink()


# 需要导入的Mock
from unittest.mock import MagicMock


# 运行测试的命令：
# pytest tests/security/test_medium_priority_fixes.py -v
