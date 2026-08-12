"""Tests for the refactor cleanup inventory gate."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest
from packaging.version import Version

from scripts.inventory_refactor_targets import _allowlisted_paths, collect_inventory, main


def _write_project(repo: Path, classifications: list[dict[str, str]]) -> None:
    (repo / "pyproject.toml").write_text(
        "[project]\nname = 'example'\nversion = '0.6.2.1'\n", encoding="utf-8"
    )
    (repo / "allowlist.json").write_text(
        json.dumps({"allowlist": [], "module_classifications": classifications}), encoding="utf-8"
    )


def _classification(path: str, **overrides: str) -> dict[str, str]:
    entry = {
        "path": path,
        "classification": "capability",
        "owner": "platform",
        "replacement": "app/current.py",
        "remove_when": "after migration",
        "expires_in_release": "0.7.0",
    }
    entry.update(overrides)
    return entry


def test_cli_fails_and_reports_direct_modules_missing_classification(tmp_path: Path) -> None:
    """Omitting a direct app/agents or app/api module must fail the governance gate."""
    agents = tmp_path / "app" / "agents"
    api = tmp_path / "app" / "api"
    agents.mkdir(parents=True)
    api.mkdir(parents=True)
    for path in (agents / "__init__.py", agents / "tracked.py", api / "__init__.py", api / "missing.py"):
        path.write_text("VALUE = 1\n", encoding="utf-8")
    nested = agents / "nested"
    nested.mkdir()
    (nested / "ignored.py").write_text("VALUE = 1\n", encoding="utf-8")
    _write_project(
        tmp_path,
        [_classification("app/agents/__init__.py"), _classification("app/api/__init__.py")],
    )

    assert main(["--json", "inventory.json", "--allowlist", "allowlist.json"], repo=tmp_path) == 1

    report = json.loads((tmp_path / "inventory.json").read_text(encoding="utf-8"))
    assert report["unclassified_modules"] == ["app/agents/tracked.py", "app/api/missing.py"]
    assert report["stale_module_classifications"] == []
    assert report["expired_module_classifications"] == []


def test_cli_reports_stale_and_expired_module_classifications(tmp_path: Path) -> None:
    """Classifications for absent paths or current releases cannot pass the gate."""
    agents = tmp_path / "app" / "agents"
    agents.mkdir(parents=True)
    (agents / "__init__.py").write_text("", encoding="utf-8")
    (agents / "legacy.py.deprecated").write_text("", encoding="utf-8")
    _write_project(
        tmp_path,
        [
            _classification("app/agents/__init__.py"),
            _classification("app/agents/legacy.py.deprecated", expires_in_release="0.6.2.1"),
            _classification("app/agents/no_longer_here.py"),
        ],
    )

    assert main(["--json", "inventory.json", "--allowlist", "allowlist.json"], repo=tmp_path) == 1

    report = json.loads((tmp_path / "inventory.json").read_text(encoding="utf-8"))
    assert report["unclassified_modules"] == []
    assert report["stale_module_classifications"] == ["app/agents/no_longer_here.py"]
    assert report["expired_module_classifications"] == ["app/agents/legacy.py.deprecated"]


@pytest.mark.parametrize(
    "entry",
    [
        _classification("app\\agents\\__init__.py"),
        _classification("app/agents/__init__.py", classification="unknown"),
        _classification("app/agents/__init__.py", owner=" "),
    ],
)
def test_cli_rejects_invalid_module_classification_entry(tmp_path: Path, entry: dict[str, str]) -> None:
    """Malformed classification metadata must not silently degrade into an exemption."""
    agents = tmp_path / "app" / "agents"
    agents.mkdir(parents=True)
    (agents / "__init__.py").write_text("", encoding="utf-8")
    _write_project(tmp_path, [entry])

    assert main(["--json", "inventory.json", "--allowlist", "allowlist.json"], repo=tmp_path) == 1


def test_cli_rejects_duplicate_module_classification_paths(tmp_path: Path) -> None:
    """A module must have one authoritative classification, not competing records."""
    agents = tmp_path / "app" / "agents"
    agents.mkdir(parents=True)
    (agents / "__init__.py").write_text("", encoding="utf-8")
    entry = _classification("app/agents/__init__.py")
    _write_project(tmp_path, [entry, entry.copy()])

    assert main(["--json", "inventory.json", "--allowlist", "allowlist.json"], repo=tmp_path) == 1


def test_unreferenced_python_module_is_reported(tmp_path: Path) -> None:
    legacy = tmp_path / "app" / "legacy"
    legacy.mkdir(parents=True)
    (legacy / "unused.py").write_text("VALUE = 1\n", encoding="utf-8")
    (tmp_path / "app" / "main.py").write_text("VALUE = 2\n", encoding="utf-8")

    inventory = collect_inventory(tmp_path, set())

    assert "app/legacy/unused.py" in inventory["unreferenced_modules"]
    assert inventory["expired_allowlist"] == []


def test_allowlist_entry_missing_required_field_is_rejected(tmp_path: Path) -> None:
    """A compatibility exemption without its removal owner or deadline is invalid."""
    config_path = tmp_path / "allowlist.json"
    config_path.write_text(
        json.dumps(
            {
                "allowlist": [
                    {
                        "path": "app/legacy.py",
                        "owner": "platform",
                        "replacement": "app/current.py",
                        "remove_when": "after migration",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="expires_in_release"):
        _allowlisted_paths(config_path, Version("0.6.2.1"))


def test_expired_allowlist_entry_is_reported_and_not_exempted(tmp_path: Path) -> None:
    """An exemption expiring in the current release cannot hide a legacy target."""
    config_path = tmp_path / "allowlist.json"
    config_path.write_text(
        json.dumps(
            {
                "allowlist": [
                    {
                        "path": "app/legacy.py",
                        "owner": "platform",
                        "replacement": "app/current.py",
                        "remove_when": "after migration",
                        "expires_in_release": "0.6.2.1",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    paths, expired = _allowlisted_paths(config_path, Version("0.6.2.1"))

    assert paths == set()
    assert expired == ["app/legacy.py"]


def test_cli_returns_nonzero_and_writes_expired_allowlist_report(tmp_path: Path) -> None:
    """The inventory gate must fail CI when a compatibility exemption has expired."""
    (tmp_path / "app").mkdir()
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'example'\nversion = '1.0.0'\n", encoding="utf-8"
    )
    config_path = tmp_path / "allowlist.json"
    config_path.write_text(
        json.dumps(
            {
                "allowlist": [
                    {
                        "path": "app/legacy.py",
                        "owner": "platform",
                        "replacement": "app/current.py",
                        "remove_when": "after migration",
                        "expires_in_release": "1.0.0",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assert main(["--json", "inventory.json", "--allowlist", "allowlist.json"], repo=tmp_path) == 1
    report = json.loads((tmp_path / "inventory.json").read_text(encoding="utf-8"))
    assert report["expired_allowlist"] == ["app/legacy.py"]


def test_cli_returns_nonzero_and_reports_missing_allowlist_field(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    """A malformed compatibility exemption must fail the command-line governance gate."""
    (tmp_path / "pyproject.toml").write_text(
        "[project]\nname = 'example'\nversion = '1.0.0'\n", encoding="utf-8"
    )
    (tmp_path / "allowlist.json").write_text(
        json.dumps(
            {
                "allowlist": [
                    {
                        "path": "app/legacy.py",
                        "owner": "platform",
                        "replacement": "app/current.py",
                        "remove_when": "after migration",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    assert main(["--json", "inventory.json", "--allowlist", "allowlist.json"], repo=tmp_path) == 1

    assert "allowlist governance error" in capsys.readouterr().err


@pytest.mark.parametrize("filename", ["test_web_activity_quick.py", "test_web_activity_system.py"])
def test_web_activity_diagnostic_module_import_has_no_output_or_filesystem_io(tmp_path: Path, filename: str) -> None:
    """Importing a pytest test module must not launch its manual diagnostics."""
    repo = Path(__file__).resolve().parents[2]
    source = repo / "tests" / filename
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import importlib.util, sys; "
                "spec = importlib.util.spec_from_file_location('diagnostic_module', sys.argv[1]); "
                "module = importlib.util.module_from_spec(spec); "
                "spec.loader.exec_module(module); "
                "print('__DIAGNOSTIC_IMPORT_COMPLETED__')"
            ),
            str(source),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout == "__DIAGNOSTIC_IMPORT_COMPLETED__\n"
    assert result.stderr == ""
    assert list(tmp_path.iterdir()) == []
