from datetime import datetime, timedelta
from pathlib import Path

from app.services.web_activity.data_manager import WebActivityDataManager


def test_archive_reports_partial_failure(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    old_date = (datetime.now() - timedelta(days=60)).strftime("%Y%m%d")
    log_file = log_dir / f"web_activity_{old_date}.jsonl"
    log_file.write_text("{}\n", encoding="utf-8")
    manager = WebActivityDataManager(
        log_dir=str(log_dir),
        backup_dir=str(tmp_path / "backups"),
        archive_dir=str(tmp_path / "archives"),
    )

    original_unlink = Path.unlink

    def fail_log_unlink(path, *args, **kwargs):
        if path == log_file:
            raise OSError("disk error")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_log_unlink)

    result = manager.archive_old_logs(days=30)

    assert result["success"] is False
    assert result["failed_count"] == 1
    assert result["archived_count"] == 0


def test_cleanup_reports_partial_failure(tmp_path, monkeypatch):
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    old_date = (datetime.now() - timedelta(days=120)).strftime("%Y%m%d")
    log_file = log_dir / f"web_activity_{old_date}.jsonl"
    log_file.write_text("{}\n", encoding="utf-8")
    manager = WebActivityDataManager(
        log_dir=str(log_dir),
        backup_dir=str(tmp_path / "backups"),
        archive_dir=str(tmp_path / "archives"),
    )

    original_unlink = Path.unlink

    def fail_log_unlink(path, *args, **kwargs):
        if path == log_file:
            raise OSError("disk error")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_log_unlink)

    result = manager.clean_old_logs(days=90)

    assert result["success"] is False
    assert result["failed_count"] == 1
    assert result["deleted_count"] == 0
