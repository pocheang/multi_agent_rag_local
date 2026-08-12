"""Inventory legacy refactor targets without deleting or rewriting them."""

from __future__ import annotations

import argparse
import ast
import json
import sys
import tomllib
from pathlib import Path

from packaging.version import InvalidVersion, Version

MODULE_CLASSIFICATIONS = frozenset(
    {
        "capability",
        "shared",
        "compatibility",
        "legacy_adapter",
        "historical_debt",
        "delete_candidate",
    }
)
MODULE_CLASSIFICATION_REQUIRED_FIELDS = {
    "path",
    "classification",
    "owner",
    "replacement",
    "remove_when",
    "expires_in_release",
}


def _module_name(path: Path) -> str:
    return ".".join(path.with_suffix("").parts)


def _imports(path: Path) -> set[str]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError, UnicodeDecodeError):
        return set()
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
            imported.update(f"{node.module}.{alias.name}" for alias in node.names if alias.name != "*")
    return imported


def _governed_module_paths(repo: Path) -> set[str]:
    """Return direct Python module files that require a governance classification."""
    paths: set[str] = set()
    for directory in ("app/agents", "app/api"):
        root = repo / directory
        for pattern in ("*.py", "*.py.deprecated"):
            paths.update(path.relative_to(repo).as_posix() for path in root.glob(pattern) if path.is_file())
    return paths


def collect_inventory(
    repo: Path,
    allowlist: set[str],
    expired_allowlist: list[str] | None = None,
    module_classifications: set[str] | None = None,
    expired_module_classifications: list[str] | None = None,
) -> dict[str, list[str]]:
    """Report unreferenced modules and oversized production files deterministically."""
    app_root = repo / "app"
    source_files = sorted(path for path in app_root.rglob("*.py") if path.name != "__init__.py")
    imports = set().union(*(_imports(path) for path in source_files)) if source_files else set()
    modules = {path: _module_name(path.relative_to(repo)) for path in source_files}
    unreferenced = [
        path.relative_to(repo).as_posix()
        for path, module in modules.items()
        if module not in imports and not any(imported.startswith(f"{module}.") for imported in imports)
        and path.relative_to(repo).as_posix() not in allowlist
    ]
    oversized = [
        path.relative_to(repo).as_posix()
        for path in source_files
        if sum(1 for _ in path.open(encoding="utf-8")) > 300 and path.relative_to(repo).as_posix() not in allowlist
    ]
    classified_paths = module_classifications or set()
    governed_paths = _governed_module_paths(repo)
    return {
        "unreferenced_modules": unreferenced,
        "oversized_files": oversized,
        "expired_allowlist": sorted(expired_allowlist or []),
        "unclassified_modules": sorted(governed_paths - classified_paths),
        "stale_module_classifications": sorted(classified_paths - governed_paths),
        "expired_module_classifications": sorted(expired_module_classifications or []),
    }


def _allowlisted_paths(config_path: Path, project_version: Version) -> tuple[set[str], list[str]]:
    if not config_path.exists():
        return set(), []
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    entries = payload.get("allowlist", []) if isinstance(payload, dict) else []
    required = {"path", "owner", "replacement", "remove_when", "expires_in_release"}
    paths: set[str] = set()
    expired: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("allowlist entries must be objects")
        missing = sorted(field for field in required if not isinstance(entry.get(field), str) or not entry[field].strip())
        if missing:
            raise ValueError(f"allowlist entry missing required fields: {missing}")
        path = entry["path"].strip()
        try:
            expiry = Version(entry["expires_in_release"].strip())
        except InvalidVersion as error:
            raise ValueError(f"allowlist entry has invalid expires_in_release for {path}: {error}") from error
        if expiry <= project_version:
            expired.append(path)
        else:
            paths.add(path)
    return paths, expired


def _module_classification_paths(config_path: Path, project_version: Version) -> tuple[set[str], list[str]]:
    """Validate module classifications without granting retrieval inventory exemptions."""
    if not config_path.exists():
        return set(), []
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    entries = payload.get("module_classifications", []) if isinstance(payload, dict) else []
    if not isinstance(entries, list):
        raise ValueError("module_classifications must be a list")

    paths: set[str] = set()
    expired: list[str] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError("module_classification entries must be objects")
        missing = sorted(
            field
            for field in MODULE_CLASSIFICATION_REQUIRED_FIELDS
            if not isinstance(entry.get(field), str) or not entry[field].strip()
        )
        if missing:
            raise ValueError(f"module_classification entry missing required fields: {missing}")

        path = entry["path"]
        if path != path.strip() or "\\" in path or Path(path).as_posix() != path:
            raise ValueError(f"module_classification path must be a POSIX path: {path}")
        if path in paths:
            raise ValueError(f"module_classification paths must be unique: {path}")
        classification = entry["classification"].strip()
        if classification not in MODULE_CLASSIFICATIONS:
            raise ValueError(f"module_classification has invalid classification for {path}: {classification}")
        try:
            expiry = Version(entry["expires_in_release"].strip())
        except InvalidVersion as error:
            raise ValueError(f"module_classification has invalid expires_in_release for {path}: {error}") from error
        paths.add(path)
        if expiry <= project_version:
            expired.append(path)
    return paths, expired


def _project_version(repo: Path) -> Version:
    try:
        payload = tomllib.loads((repo / "pyproject.toml").read_text(encoding="utf-8"))
        raw_version = payload["project"]["version"]
        return Version(raw_version)
    except (KeyError, OSError, TypeError, tomllib.TOMLDecodeError, InvalidVersion) as error:
        raise ValueError(f"could not read a valid [project].version: {error}") from error


def main(argv: list[str] | None = None, repo: Path | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create a non-destructive refactor inventory.")
    parser.add_argument("--json", required=True, dest="output")
    parser.add_argument("--allowlist", default="config/refactor_cleanup_allowlist.json")
    args = parser.parse_args(argv)
    repo = repo or Path(__file__).resolve().parents[1]
    try:
        project_version = _project_version(repo)
        allowlist, expired_allowlist = _allowlisted_paths(repo / args.allowlist, project_version)
        classifications, expired_classifications = _module_classification_paths(
            repo / args.allowlist, project_version
        )
    except (json.JSONDecodeError, ValueError) as error:
        print(f"allowlist governance error: {error}", file=sys.stderr)
        return 1
    inventory = collect_inventory(
        repo,
        allowlist,
        expired_allowlist,
        classifications,
        expired_classifications,
    )
    output = repo / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    governance_failures = {
        "expired allowlist entries": inventory["expired_allowlist"],
        "unclassified modules": inventory["unclassified_modules"],
        "stale module classifications": inventory["stale_module_classifications"],
        "expired module classifications": inventory["expired_module_classifications"],
    }
    failures = [f"{label}: {', '.join(paths)}" for label, paths in governance_failures.items() if paths]
    if failures:
        print(f"allowlist governance error: {'; '.join(failures)}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
