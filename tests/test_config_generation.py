from pathlib import Path

import pytest

from deploy.scripts.config import (
    generate_secrets,
    merge_env_files,
    render_environment,
    validate_environment,
)


def write_env(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def test_later_layers_override_earlier_layers(tmp_path):
    base = write_env(tmp_path / "base.env", "APP_ENV=dev\nQUERY_MAX_CONCURRENT=8\n")
    profile = write_env(tmp_path / "profile.env", "QUERY_MAX_CONCURRENT=24\n")
    assert merge_env_files((base, profile))["QUERY_MAX_CONCURRENT"] == "24"


def test_duplicate_key_inside_one_file_is_rejected(tmp_path):
    path = write_env(tmp_path / "invalid.env", "APP_ENV=dev\nAPP_ENV=test\n")
    with pytest.raises(ValueError, match="duplicate environment key APP_ENV"):
        merge_env_files((path,))


def test_production_requires_openai_key_for_openai_backend():
    errors = validate_environment(
        {"APP_ENV": "production", "MODEL_BACKEND": "openai", "OPENAI_API_KEY": ""},
        "production",
    )
    assert "OPENAI_API_KEY is required when MODEL_BACKEND=openai" in errors


def test_development_accepts_ollama_without_api_key():
    errors = validate_environment(
        {"APP_ENV": "development", "MODEL_BACKEND": "ollama", "OLLAMA_BASE_URL": "http://localhost:11434"},
        "development",
    )
    assert errors == []


def test_generate_secrets_reuses_existing_values(tmp_path):
    path = tmp_path / "generated-secrets.env"
    first = generate_secrets(path)
    second = generate_secrets(path)
    assert first == second
    assert path.read_text(encoding="utf-8").count("POSTGRES_PASSWORD=") == 1


def test_render_environment_merges_templates_and_process_override(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / "config" / "env").mkdir(parents=True)
    (root / "config" / "profiles").mkdir(parents=True)
    (root / ".runtime").mkdir()
    write_env(root / "config" / "env" / "base.env", "APP_ENV=dev\nMODEL_BACKEND=ollama\nQUERY_MAX_CONCURRENT=8\n")
    write_env(root / "config" / "env" / "test.env.example", "APP_ENV=test\n")
    write_env(root / "config" / "profiles" / "fast.env", "QUERY_MAX_CONCURRENT=32\n")
    write_env(root / ".runtime" / "generated-secrets.env", "JWT_SECRET_KEY=runtime-secret\n")
    monkeypatch.setenv("QUERY_MAX_CONCURRENT", "64")
    output = tmp_path / "rendered.env"
    values = render_environment("test", "fast", output, root)
    assert values["APP_ENV"] == "test"
    assert values["QUERY_MAX_CONCURRENT"] == "64"
    assert values["JWT_SECRET_KEY"] == "runtime-secret"
    assert "QUERY_MAX_CONCURRENT=64" in output.read_text(encoding="utf-8")
