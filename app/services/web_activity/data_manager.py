"""
Web Activity Data Management

数据备份、归档和清理系统。

功能：
- 自动备份日志文件
- 压缩归档旧数据
- 定期清理过期日志
- 数据恢复
"""

import gzip
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger("app.agents.web_activity_data_manager")


class WebActivityDataManager:
    """
    Web活动数据管理器

    负责日志文件的备份、归档和清理
    """

    def __init__(
        self,
        log_dir: str = "logs/web_activity",
        backup_dir: str = "backups/web_activity",
        archive_dir: str = "archives/web_activity",
    ):
        """
        初始化数据管理器

        Args:
            log_dir: 日志文件目录
            backup_dir: 备份目录
            archive_dir: 归档目录
        """
        self.log_dir = Path(log_dir)
        self.backup_dir = Path(backup_dir)
        self.archive_dir = Path(archive_dir)

        # 创建目录
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self.archive_dir.mkdir(parents=True, exist_ok=True)

        logger.info("WebActivityDataManager initialized")

    def backup_logs(self, days: int = 7) -> dict:
        """
        备份最近N天的日志

        Args:
            days: 备份最近几天的日志

        Returns:
            备份结果字典
        """
        logger.info(f"Starting backup for last {days} days")

        backup_date = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"web_activity_backup_{backup_date}.tar.gz"
        backup_path = self.backup_dir / backup_name

        # 收集要备份的文件
        cutoff_date = datetime.now() - timedelta(days=days)
        files_to_backup = []

        for log_file in self.log_dir.glob("web_activity_*.jsonl"):
            try:
                # 从文件名提取日期
                date_str = log_file.stem.replace("web_activity_", "")
                file_date = datetime.strptime(date_str, "%Y%m%d")

                if file_date >= cutoff_date:
                    files_to_backup.append(log_file)
            except ValueError:
                logger.warning(f"Skip file with invalid date format: {log_file}")

        if not files_to_backup:
            logger.warning("No files to backup")
            return {"success": False, "message": "No files to backup", "file_count": 0}

        # 创建tar.gz备份
        import tarfile

        try:
            with tarfile.open(backup_path, "w:gz") as tar:
                for file in files_to_backup:
                    tar.add(file, arcname=file.name)

            logger.info(f"Backup created: {backup_path} ({len(files_to_backup)} files)")

            return {
                "success": True,
                "backup_file": str(backup_path),
                "file_count": len(files_to_backup),
                "backup_size": backup_path.stat().st_size,
            }
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return {"success": False, "message": str(e), "file_count": 0}

    def archive_old_logs(self, days: int = 30) -> dict:
        """
        归档超过N天的日志（压缩）

        Args:
            days: 归档超过几天的日志

        Returns:
            归档结果字典
        """
        logger.info(f"Starting archive for logs older than {days} days")

        cutoff_date = datetime.now() - timedelta(days=days)
        archived_files = []
        failed_files = []

        for log_file in self.log_dir.glob("web_activity_*.jsonl"):
            try:
                # 从文件名提取日期
                date_str = log_file.stem.replace("web_activity_", "")
                file_date = datetime.strptime(date_str, "%Y%m%d")

                if file_date < cutoff_date:
                    # 压缩并移动到归档目录
                    archive_path = self.archive_dir / f"{log_file.name}.gz"

                    with open(log_file, "rb") as f_in:
                        with gzip.open(archive_path, "wb") as f_out:
                            shutil.copyfileobj(f_in, f_out)

                    # 删除原文件
                    log_file.unlink()

                    archived_files.append(
                        {
                            "original": str(log_file),
                            "archived": str(archive_path),
                            "date": file_date.strftime("%Y-%m-%d"),
                        }
                    )

                    logger.info(f"Archived: {log_file.name}")

            except ValueError:
                logger.warning(f"Skip file with invalid date format: {log_file}")
            except Exception as e:
                logger.error(f"Failed to archive {log_file}: {e}")
                failed_files.append({"file": str(log_file), "error": str(e)})

        return {
            "success": not failed_files,
            "archived_count": len(archived_files),
            "failed_count": len(failed_files),
            "failures": failed_files,
            "files": archived_files,
        }

    def clean_old_logs(self, days: int = 90) -> dict:
        """
        删除超过N天的日志

        Args:
            days: 删除超过几天的日志

        Returns:
            清理结果字典
        """
        logger.info(f"Starting cleanup for logs older than {days} days")

        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_files = []
        failed_files = []

        # 清理未压缩的日志
        for log_file in self.log_dir.glob("web_activity_*.jsonl"):
            try:
                date_str = log_file.stem.replace("web_activity_", "")
                file_date = datetime.strptime(date_str, "%Y%m%d")

                if file_date < cutoff_date:
                    log_file.unlink()
                    deleted_files.append(str(log_file))
                    logger.info(f"Deleted: {log_file.name}")

            except ValueError:
                pass
            except Exception as e:
                logger.error(f"Failed to delete {log_file}: {e}")
                failed_files.append({"file": str(log_file), "error": str(e)})

        # 清理归档文件
        for archive_file in self.archive_dir.glob("web_activity_*.jsonl.gz"):
            try:
                date_str = archive_file.stem.replace("web_activity_", "").replace(".jsonl", "")
                file_date = datetime.strptime(date_str, "%Y%m%d")

                if file_date < cutoff_date:
                    archive_file.unlink()
                    deleted_files.append(str(archive_file))
                    logger.info(f"Deleted archived: {archive_file.name}")

            except ValueError:
                pass
            except Exception as e:
                logger.error(f"Failed to delete {archive_file}: {e}")
                failed_files.append({"file": str(archive_file), "error": str(e)})

        return {
            "success": not failed_files,
            "deleted_count": len(deleted_files),
            "failed_count": len(failed_files),
            "failures": failed_files,
            "files": deleted_files,
        }

    def clean_old_backups(self, days: int = 30) -> dict:
        """
        删除超过N天的备份文件

        Args:
            days: 删除超过几天的备份

        Returns:
            清理结果字典
        """
        logger.info(f"Starting cleanup for backups older than {days} days")

        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_backups = []
        failed_backups = []

        for backup_file in self.backup_dir.glob("web_activity_backup_*.tar.gz"):
            try:
                # 获取文件修改时间
                mtime = datetime.fromtimestamp(backup_file.stat().st_mtime)

                if mtime < cutoff_date:
                    backup_file.unlink()
                    deleted_backups.append(str(backup_file))
                    logger.info(f"Deleted backup: {backup_file.name}")

            except Exception as e:
                logger.error(f"Failed to delete backup {backup_file}: {e}")
                failed_backups.append({"file": str(backup_file), "error": str(e)})

        return {
            "success": not failed_backups,
            "deleted_count": len(deleted_backups),
            "failed_count": len(failed_backups),
            "failures": failed_backups,
            "files": deleted_backups,
        }

    def restore_backup(self, backup_file: str) -> dict:
        """
        从备份恢复数据

        Args:
            backup_file: 备份文件路径

        Returns:
            恢复结果字典
        """
        import tarfile

        backup_path = Path(backup_file)
        if not backup_path.exists():
            return {"success": False, "message": f"Backup file not found: {backup_file}"}

        try:
            restored_files = []

            with tarfile.open(backup_path, "r:gz") as tar:
                for member in tar.getmembers():
                    # 恢复到日志目录
                    tar.extract(member, self.log_dir)
                    restored_files.append(member.name)
                    logger.info(f"Restored: {member.name}")

            return {"success": True, "restored_count": len(restored_files), "files": restored_files}

        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return {"success": False, "message": str(e)}

    def get_storage_info(self) -> dict:
        """
        获取存储空间信息

        Returns:
            存储信息字典
        """

        def get_dir_size(path: Path) -> int:
            """计算目录大小"""
            total = 0
            if path.exists():
                for file in path.rglob("*"):
                    if file.is_file():
                        total += file.stat().st_size
            return total

        def get_file_count(path: Path, pattern: str = "*") -> int:
            """计算文件数量"""
            if path.exists():
                return len(list(path.glob(pattern)))
            return 0

        return {
            "log_dir": {
                "path": str(self.log_dir),
                "size_bytes": get_dir_size(self.log_dir),
                "file_count": get_file_count(self.log_dir, "*.jsonl"),
            },
            "archive_dir": {
                "path": str(self.archive_dir),
                "size_bytes": get_dir_size(self.archive_dir),
                "file_count": get_file_count(self.archive_dir, "*.gz"),
            },
            "backup_dir": {
                "path": str(self.backup_dir),
                "size_bytes": get_dir_size(self.backup_dir),
                "file_count": get_file_count(self.backup_dir, "*.tar.gz"),
            },
        }

    def scheduled_maintenance(self):
        """
        定期维护任务（建议通过cron定期执行）

        执行：
        1. 备份最近7天的日志
        2. 归档30天前的日志
        3. 清理90天前的日志
        4. 清理30天前的备份
        """
        logger.info("Starting scheduled maintenance")

        results = {}

        # 1. 备份
        results["backup"] = self.backup_logs(days=7)

        # 2. 归档
        results["archive"] = self.archive_old_logs(days=30)

        # 3. 清理旧日志
        results["clean_logs"] = self.clean_old_logs(days=90)

        # 4. 清理旧备份
        results["clean_backups"] = self.clean_old_backups(days=30)

        logger.info("Scheduled maintenance completed")

        return results


# 全局实例
_global_data_manager = None


def get_data_manager() -> WebActivityDataManager:
    """获取全局数据管理器实例"""
    global _global_data_manager
    if _global_data_manager is None:
        _global_data_manager = WebActivityDataManager()
    return _global_data_manager
