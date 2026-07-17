from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_configuration_governance_docs_point_to_canonical_directories():
    config_doc = (ROOT / "config" / "README.md").read_text(encoding="utf-8")
    deploy_doc = (ROOT / "deploy" / "README.md").read_text(encoding="utf-8")
    guide = (ROOT / "docs" / "zh-CN" / "guides" / "configuration-governance.md").read_text(encoding="utf-8")

    assert "config/env" in config_doc
    assert "deploy/compose" in deploy_doc
    assert "deploy/scripts/deploy" in guide
    assert ".runtime/" in guide
    assert "docker-compose up" not in guide
