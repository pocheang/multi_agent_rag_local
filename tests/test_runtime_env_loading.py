import importlib


def test_settings_reads_explicit_runtime_env_file(monkeypatch, tmp_path):
    runtime_file = tmp_path / "runtime.env"
    runtime_file.write_text("APP_ENV=test\nMODEL_BACKEND=ollama\n", encoding="utf-8")
    monkeypatch.setenv("RUNTIME_ENV_FILE", str(runtime_file))

    from app.core import config as config_module

    importlib.reload(config_module)
    settings = config_module.Settings()

    assert settings.app_env == "test"
    assert settings.model_backend == "ollama"

    monkeypatch.delenv("RUNTIME_ENV_FILE")
    importlib.reload(config_module)
