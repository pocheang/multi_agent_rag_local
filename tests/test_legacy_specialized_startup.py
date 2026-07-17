from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_specialized_windows_startup_wrappers_are_repository_relative():
    for name in ("start-backend.ps1", "start-frontend.ps1"):
        content = (ROOT / name).read_text(encoding="utf-8", errors="replace")
        assert "$PSScriptRoot" in content
        assert "C:\\Users\\pocheang" not in content
