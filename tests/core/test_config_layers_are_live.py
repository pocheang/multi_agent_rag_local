"""A key in a configuration layer that `Settings` does not know is dead.

`Settings` validates by alias and carries `extra="ignore"`, so a key in
`config/env/*` or `config/profiles/*` that matches no alias is dropped without a
word: no error, no warning, and the render step copies it into
`.runtime/{APP_ENV}.env` where it looks exactly like a live setting.

That is the same silence this repository has now met four times -- an admin page
reporting an environment variable nothing read, a settings source returning
field-name keys, a compose file naming a database the app never opened, and this.
Two keys were found by looking: `QUERY_RESULT_CACHE_BACKEND`, a sibling of the
real `RETRIEVAL_CACHE_BACKEND` that was never implemented, and `DEBUG`, which had
no reader at all -- while `deploy/scripts/config.py` enforced "DEBUG must not be
true in production", a safety rule about a value that could not have any effect.

The allowlist below is for keys the *deployment* consumes -- compose
interpolation and the secret generator -- which legitimately never reach
`Settings`.
"""

from __future__ import annotations

import pathlib

from app.core.config import Settings
from app.core.remote_config import parse_properties

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]

# Read by docker compose or by deploy/scripts/config.py, never by Settings.
DEPLOYMENT_ONLY = {
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "NEO4J_PASSWORD",
    "REDIS_PASSWORD",
    "ADMIN_CREATE_APPROVAL_TOKEN",
    "ADMIN_CREATE_APPROVAL_TOKEN_HASH",
    "N8N_DB",
    "VITE_API_BASE_URL",
    "RUNTIME_ENV_FILE",
}


def _layer_files() -> list[pathlib.Path]:
    """The committed layers. `.env` without `.example` is a local override."""

    return sorted(path for path in (REPO_ROOT / "config").rglob("*.env*") if path.name.endswith(".example"))


def test_every_layer_key_reaches_settings() -> None:
    aliases = {(field.alias or name) for name, field in Settings.model_fields.items()}

    dead: dict[str, list[str]] = {}
    for path in _layer_files():
        values = parse_properties(path.read_text(encoding="utf-8"))
        unknown = sorted(key for key in values if key not in aliases and key not in DEPLOYMENT_ONLY)
        if unknown:
            dead[path.relative_to(REPO_ROOT).as_posix()] = unknown

    assert not dead, (
        "These keys are dropped silently -- Settings validates by alias and ignores the rest:\n  "
        + "\n  ".join(f"{path}: {', '.join(keys)}" for path, keys in dead.items())
        + "\nAdd the field to Settings, correct the spelling, or list it in DEPLOYMENT_ONLY "
        "if the deployment consumes it directly."
    )


def test_the_layers_are_not_empty() -> None:
    """A guard that reads no files would pass forever."""

    files = _layer_files()
    assert len(files) >= 6, files
    assert any(parse_properties(path.read_text(encoding="utf-8")) for path in files)
