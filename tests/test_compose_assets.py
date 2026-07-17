from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_production_compose_uses_pinned_images_and_no_database_ports():
    compose = ROOT / "deploy" / "compose" / "compose.yaml"
    assert compose.is_file()
    text = compose.read_text(encoding="utf-8")
    assert ":latest" not in text
    assert '"5432:5432"' not in text
    assert '"7687:7687"' not in text
    assert '"6379:6379"' not in text


def test_compose_files_reference_canonical_observability_config():
    compose = ROOT / "deploy" / "compose" / "compose.monitoring.yaml"
    assert compose.is_file()
    text = compose.read_text(encoding="utf-8")
    assert "config/observability/prometheus" in text
    assert "config/observability/grafana" in text
    assert "config/observability/alertmanager" in text
