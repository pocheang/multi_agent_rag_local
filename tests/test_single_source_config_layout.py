from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_repository_has_no_root_legacy_configuration_or_startup_aliases():
    forbidden = (
        ".env.example",
        ".env.docker.example",
        ".env.docling.example",
        ".env.optimized",
        ".env.optimized.recommended",
        ".env.security",
        "docker-compose.yml",
        "docker-compose.dev.yml",
        "docker-compose.monitoring.yml",
        "start.sh",
        "start.bat",
        "start-all.ps1",
        "start-backend.ps1",
        "start-frontend.ps1",
        "restart.bat",
    )
    assert all(not (ROOT / name).exists() for name in forbidden)


def test_repository_has_no_legacy_configuration_directory():
    assert not (ROOT / "config" / "legacy").exists()
    assert not (ROOT / "configs").exists()


def test_documentation_points_only_to_canonical_config_and_deploy_paths():
    paths = (
        ROOT / "README.md",
        ROOT / "config" / "README.md",
        ROOT / "deploy" / "README.md",
        ROOT / "docs" / "zh-CN" / "guides" / "configuration-governance.md",
    )
    text = "\n".join(path.read_text(encoding="utf-8") for path in paths)
    assert "config/legacy" not in text
    assert "compatibility wrapper" not in text.lower()
