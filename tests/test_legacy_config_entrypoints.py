from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_root_compose_files_delegate_to_canonical_compose_assets():
    for name in ("docker-compose.yml", "docker-compose.dev.yml", "docker-compose.monitoring.yml"):
        content = (ROOT / name).read_text(encoding="utf-8")
        assert "deploy/compose/" in content


def test_root_startup_files_delegate_without_machine_specific_paths_or_process_kills():
    for name in ("start.sh", "start.bat", "start-all.ps1", "restart.bat"):
        content = (ROOT / name).read_text(encoding="utf-8", errors="replace")
        assert "deploy" in content.lower()
        assert "C:\\Users\\pocheang" not in content
        assert "taskkill" not in content.lower()


def test_duplicate_runtime_profiles_are_removed_after_migration():
    duplicate_dir = ROOT / "configs" / "runtime-profiles"
    assert not any(duplicate_dir.glob("*.env"))


def test_canonical_deployment_assets_are_pinned():
    compose_text = "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "deploy" / "compose").glob("*.yaml"))
    assert ":latest" not in compose_text
