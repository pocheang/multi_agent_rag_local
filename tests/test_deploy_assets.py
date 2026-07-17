from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_canonical_configuration_layout_exists():
    expected = (
        ROOT / "config" / "env" / "base.env",
        ROOT / "config" / "env" / "development.env.example",
        ROOT / "config" / "env" / "test.env.example",
        ROOT / "config" / "env" / "production.env.example",
        ROOT / "config" / "profiles" / "fast.env",
        ROOT / "config" / "profiles" / "balanced.env",
        ROOT / "config" / "profiles" / "deep.env",
        ROOT / "config" / "application" / "router_calibration.json",
        ROOT / "config" / "application" / "web_activity_config.json",
        ROOT / "config" / "observability" / "prometheus" / "prometheus.yml",
        ROOT / "config" / "observability" / "grafana" / "datasources.yml",
        ROOT / "config" / "observability" / "alertmanager" / "alertmanager.yml",
    )
    missing = [str(path.relative_to(ROOT)) for path in expected if not path.is_file()]
    assert missing == []


def test_profiles_do_not_define_provider_secrets():
    forbidden = {
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "POSTGRES_PASSWORD",
        "NEO4J_PASSWORD",
        "REDIS_PASSWORD",
    }
    for profile in (ROOT / "config" / "profiles").glob("*.env"):
        names = {
            line.split("=", 1)[0].strip()
            for line in profile.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#") and "=" in line
        }
        assert names.isdisjoint(forbidden), profile
