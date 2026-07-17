from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_bash_deploy_wrapper_is_safe_and_uses_canonical_runtime_config():
    script = (ROOT / "deploy" / "scripts" / "deploy.sh").read_text(encoding="utf-8")

    assert "set -Eeuo pipefail" in script
    assert "config.py" in script
    assert "generated-secrets.env" in script
    assert "docker compose" in script
    assert "down -v" not in script


def test_powershell_deploy_wrapper_is_safe_and_uses_canonical_runtime_config():
    script = (ROOT / "deploy" / "scripts" / "deploy.ps1").read_text(encoding="utf-8")

    assert '$ErrorActionPreference = "Stop"' in script
    assert "config.py" in script
    assert "generated-secrets.env" in script
    assert "docker compose" in script
    assert "down -v" not in script
