from __future__ import annotations

import argparse
import os
import re
import secrets
import sys
from collections.abc import Iterable, Mapping
from pathlib import Path

KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
VALID_ENVIRONMENTS = {"development", "test", "production"}
VALID_PROFILES = {"fast", "balanced", "deep"}
VALID_BACKENDS = {"openai", "anthropic", "ollama", "local", "custom", "deepseek"}
SECRET_KEYS = (
    "POSTGRES_PASSWORD",
    "NEO4J_PASSWORD",
    "REDIS_PASSWORD",
    "JWT_SECRET_KEY",
    "API_SETTINGS_ENCRYPTION_KEY",
    "ADMIN_CREATE_APPROVAL_TOKEN",
)


def parse_env_file(path: Path) -> dict[str, str]:
    """Parse one dotenv file and reject duplicate keys in that file."""
    values: dict[str, str] = {}
    for number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            raise ValueError(f"invalid environment line {path}:{number}")
        key, value = line.split("=", 1)
        key = key.strip()
        if not KEY_RE.fullmatch(key):
            raise ValueError(f"invalid environment key {key!r} in {path}:{number}")
        if key in values:
            raise ValueError(f"duplicate environment key {key}")
        values[key] = value.strip().strip('"').strip("'")
    return values


def merge_env_files(paths: Iterable[Path], overrides: Mapping[str, str] | None = None) -> dict[str, str]:
    """Merge dotenv layers in order, with later layers taking precedence."""
    merged: dict[str, str] = {}
    for path in paths:
        merged.update(parse_env_file(Path(path)))
    merged.update({key: value for key, value in (overrides or {}).items() if value is not None})
    return merged


def _new_secret(key: str) -> str:
    size = 32 if key in {"POSTGRES_PASSWORD", "NEO4J_PASSWORD", "REDIS_PASSWORD"} else 48
    return secrets.token_urlsafe(size)


def generate_secrets(path: Path, existing: Mapping[str, str] | None = None) -> dict[str, str]:
    """Create missing deployment secrets and preserve every existing value."""
    values = dict(existing or {})
    if path.is_file():
        values = {**parse_env_file(path), **values}
    for key in SECRET_KEYS:
        if not str(values.get(key, "")).strip():
            values[key] = _new_secret(key)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{key}={values[key]}\n" for key in SECRET_KEYS), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return {key: values[key] for key in SECRET_KEYS}


def validate_environment(values: Mapping[str, str], environment: str) -> list[str]:
    """Return human-readable validation errors without exposing secret values."""
    errors: list[str] = []
    if environment not in VALID_ENVIRONMENTS:
        errors.append(f"unsupported environment: {environment}")
    backend = str(values.get("MODEL_BACKEND", "")).strip().lower()
    if backend not in VALID_BACKENDS:
        errors.append(f"unsupported MODEL_BACKEND: {backend or '<empty>'}")
    if environment == "production":
        if backend == "openai" and not str(values.get("OPENAI_API_KEY", "")).strip():
            errors.append("OPENAI_API_KEY is required when MODEL_BACKEND=openai")
        if backend == "anthropic" and not str(values.get("ANTHROPIC_API_KEY", "")).strip():
            errors.append("ANTHROPIC_API_KEY is required when MODEL_BACKEND=anthropic")
        if backend == "ollama" and not str(values.get("OLLAMA_BASE_URL", "")).strip():
            errors.append("OLLAMA_BASE_URL is required when MODEL_BACKEND=ollama")
        if str(values.get("DEBUG", "")).strip().lower() == "true":
            errors.append("DEBUG must not be true in production")
        origins = str(values.get("CORS_ALLOW_ORIGINS", "")).strip()
        if not origins or "*" in {part.strip() for part in origins.split(",")}:
            errors.append("CORS_ALLOW_ORIGINS must contain explicit production origins")
        for key in SECRET_KEYS:
            if not str(values.get(key, "")).strip():
                errors.append(f"{key} is required in production")
    return errors


def _write_env(path: Path, values: Mapping[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{key}={values[key]}\n" for key in sorted(values)), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass


def render_environment(environment: str, profile: str, output: Path, repo_root: Path) -> dict[str, str]:
    """Render one complete runtime environment from canonical layers."""
    if environment not in VALID_ENVIRONMENTS:
        raise ValueError(f"unsupported environment: {environment}")
    if profile not in VALID_PROFILES:
        raise ValueError(f"unsupported profile: {profile}")
    config_root = repo_root / "config"
    runtime_root = repo_root / ".runtime"
    env_file = config_root / "env" / f"{environment}.env.example"
    profile_file = config_root / "profiles" / f"{profile}.env"
    if not env_file.is_file():
        raise FileNotFoundError(env_file)
    if not profile_file.is_file():
        raise FileNotFoundError(profile_file)
    secrets_file = runtime_root / "generated-secrets.env"
    generate_secrets(secrets_file)
    layers = (config_root / "env" / "base.env", env_file, profile_file, secrets_file)
    values = merge_env_files(layers)
    override_keys = set(values) | set(SECRET_KEYS)
    values.update({key: value for key, value in os.environ.items() if key in override_keys})
    errors = validate_environment(values, environment)
    if errors:
        raise ValueError("; ".join(errors))
    _write_env(output, values)
    return values


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Render and validate QueryMind runtime configuration")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for name in ("render", "validate"):
        subparser = subparsers.add_parser(name)
        subparser.add_argument("--environment", required=True, choices=sorted(VALID_ENVIRONMENTS))
        subparser.add_argument("--profile", required=True, choices=sorted(VALID_PROFILES))
        subparser.add_argument("--output", default=".runtime/runtime.env")
    args = parser.parse_args(argv)
    try:
        values = render_environment(args.environment, args.profile, Path(args.output), _repo_root())
    except (FileNotFoundError, ValueError) as exc:
        print(f"Configuration error: {exc}", file=sys.stderr)
        return 1
    if args.command == "validate":
        print(f"Configuration valid: environment={args.environment} profile={args.profile} keys={len(values)}")
    else:
        print(f"Configuration rendered: environment={args.environment} profile={args.profile} output={args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
