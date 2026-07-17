from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_init_app_script_has_no_destructive_database_commands():
    source = (ROOT / "deploy" / "scripts" / "init_app.py").read_text(encoding="utf-8")
    assert "DROP TABLE" not in source.upper()
    assert "DELETE FROM" not in source.upper()
    assert "down -v" not in source


def test_healthcheck_script_exposes_cli_entrypoint():
    source = (ROOT / "deploy" / "scripts" / "healthcheck.py").read_text(encoding="utf-8")
    assert "--url" in source
    assert 'if __name__ == "__main__"' in source
