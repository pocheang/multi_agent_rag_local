"""Refuse to let anything sensitive reach GitHub, or a delivery copy.

Two modes, because they are two different jobs:

    python scripts/check_sensitive.py                  every tracked file (CI)
    python scripts/check_sensitive.py FILE...          just these (pre-commit)
    python scripts/check_sensitive.py --tree DIR       a delivery copy on disk

The first two read the file list from git, which is the whole point: a working
tree legitimately contains data/, logs/, .venv/ and node_modules/, all of them
gitignored. Walking the filesystem there would fail on every run. Asking git
instead turns FORBIDDEN_PATHS into a check that means something -- it catches a
`git add -f data/app.db`, which is how a database actually reaches a repository.

--tree is the delivery-copy check, where the filesystem *is* the artifact and a
gitignored directory being present means the copy was made by hand rather than
by `git clone`, or was contaminated afterwards. Running a build inside the copy
is enough to do that: ruff leaves .ruff_cache/, and importing app/ creates data/.

The two baselines below are ratchets, the same shape as KNOWN_OFFENDERS in
tests/security/ and scripts/design-scale-baseline.json: what exists today is
frozen and may shrink, anything new fails. A blanket directory allowlist was the
alternative and it was worse -- exempting all of docs/ would let a real key land
in any document in the project.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

# Tracked files must never live under these. Every one is gitignored, so a hit
# means someone forced it past that.
FORBIDDEN_PATHS = {
    "data",
    "logs",
    "internal_docs",
    "artifacts",
    "reports",
    ".runtime",
    ".venv",
    "node_modules",
    ".superpowers",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "querymind.egg-info",
}

FORBIDDEN_SUFFIXES = {
    ".db",
    ".sqlite3",
    ".sqlite",
    ".jsonl",
    ".log",
    ".key",
    ".pem",
    ".p12",
    ".pfx",
    ".crt",
    ".jwt",
}

SECRET_SHAPES = [
    ("openai key", re.compile(r"sk-(?:proj-|ant-)?[A-Za-z0-9_-]{20,}")),
    ("aws key id", re.compile(r"AKIA[0-9A-Z]{16}")),
    ("github token", re.compile(r"gh[pousr]_[A-Za-z0-9]{20,}")),
    ("slack token", re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}")),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{20,}\.")),
]

# Files that may contain a credential *shape*. These are the redaction feature's
# own fixtures and the prose describing them. Rewriting them to satisfy this
# scan would break tests/security/, and only after the suite went green -- which
# is why this check reports rather than edits.
# The last entry is this script's own test, which cannot demonstrate that a
# private-key header is caught without containing one.
SECRET_BASELINE = {
    "app/privacy/streaming.py",
    "tests/security/test_streaming_redaction.py",
    "tests/services/test_answer_safety.py",
    "tests/security/test_sensitive_content_gate.py",
    "docs/development/daily-logs/2026-08-17/streaming-and-long-text-config.md",
    "docs/superpowers/plans/2026-08-29-backend-full-audit-remediation.md",
}

# Files that quote a developer's absolute path. The two documents are session
# notes written before this check existed; neither is worth rewriting, and a new
# one is. The third is this file: LOCAL_PATH below spells out "/c/Users/", so the
# pattern matches its own source. Writing it in pieces to dodge that would make
# the one regex here that has already been got wrong twice unreadable, which is a
# bad trade for exempting a 250-line file nobody edits casually.
LOCAL_PATH_BASELINE = {
    "scripts/check_sensitive.py",
    "docs/superpowers/plans/2026-08-23-session-handoff-prompt.md",
    "docs/superpowers/plans/2026-08-29-frontend-audit-remediation.md",
}

# Case-insensitive only on the drive letter. "/Users/" stays exact: macOS home
# directories are capitalised, and matching it loosely turns every
# /admin/users/<id>/ API route in the test suite into a false positive.
LOCAL_PATH = re.compile("[Cc]:[\\\\/]{1,2}Users[\\\\/]{1,2}|/c/Users/|/Users/[a-z]+/")

TEXT_SUFFIXES = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".mjs",
    ".css",
    ".md",
    ".json",
    ".yaml",
    ".yml",
    ".toml",
    ".txt",
    ".env",
    ".example",
    ".properties",
    ".conf",
    ".sh",
    ".ps1",
    ".html",
    ".lock",
    ".gitignore",
    "",
}


def tracked_files(root: Path) -> list[str]:
    out = subprocess.run(
        ["git", "-C", str(root), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    return [line for line in out.stdout.splitlines() if line]


def tree_files(root: Path) -> list[str]:
    return [p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and ".git" not in p.parts]


def env_values(path: Path) -> list[str]:
    """Keys in an env file that carry a value. Never returns the value."""
    hits = []
    for line in path.read_text("utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        if value.strip():
            hits.append(f"{key.strip()}=<{len(value.strip())} chars>")
    return hits


def scan(root: Path, rels: list[str], expect: int | None, whole: bool) -> tuple[list[str], list[str]]:
    fails: list[str] = []
    notes: list[str] = []
    used: set[str] = set()

    for rel in rels:
        path = root / rel
        parts = set(Path(rel).parts)

        bad = FORBIDDEN_PATHS & parts
        if bad:
            joined = "/".join(sorted(bad))
            fails.append(f"[path] {rel} -- under {joined}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            fails.append(f"[type] {rel}")

        if ".env" in path.name and ".example" not in path.name and path.is_file():
            for hit in env_values(path):
                fails.append(f"[env] {rel}: {hit}")

        if path.suffix.lower() not in TEXT_SUFFIXES or not path.is_file():
            continue
        try:
            text = path.read_text("utf-8", errors="strict")
        except (UnicodeDecodeError, OSError):
            continue

        for label, pattern in SECRET_SHAPES:
            match = pattern.search(text)
            if not match:
                continue
            shown = match.group(0)[:12] + "..."
            if rel in SECRET_BASELINE:
                used.add(rel)
                notes.append(f"[baseline secret] {rel}: {label} ({shown})")
            else:
                fails.append(f"[secret] {rel}: {label} ({shown})")

        if LOCAL_PATH.search(text):
            if rel in LOCAL_PATH_BASELINE:
                used.add(rel)
                notes.append(f"[baseline local-path] {rel}")
            else:
                fails.append(f"[local-path] {rel} -- a developer's absolute path")

    # A ratchet may only shrink. An entry that no longer matches anything means
    # the exemption is wider than the code needs, and an allowlist that is never
    # pruned stops describing anything. Only meaningful on a whole-repository
    # scan: pre-commit sees a handful of staged files, where almost every entry
    # is legitimately unused.
    if whole:
        for rel in sorted((SECRET_BASELINE | LOCAL_PATH_BASELINE) - used):
            fails.append(f"[stale baseline] {rel} -- no longer matches; remove the entry")

    if expect is not None and len(rels) != expect:
        fails.append(f"[count] {len(rels)} files, expected {expect}")

    return fails, notes


def main(argv: list[str]) -> int:
    args = argv[1:]
    expect = None
    if "--expect" in args:
        i = args.index("--expect")
        expect = int(args[i + 1])
        del args[i : i + 2]

    if "--tree" in args:
        i = args.index("--tree")
        root = Path(args[i + 1]).resolve()
        del args[i : i + 2]
        if not root.is_dir():
            print(f"not a directory: {root}")
            return 2
        rels, mode, whole = tree_files(root), f"tree {root}", True
    else:
        root = Path.cwd()
        if args:
            rels, mode, whole = [Path(a).as_posix() for a in args], "given files", False
        else:
            rels, mode, whole = tracked_files(root), "tracked files", True

    fails, notes = scan(root, rels, expect, whole)

    print(f"checked {len(rels)} {mode}")
    if notes:
        print(f"\nbaseline (known, frozen): {len(notes)}")
        for note in sorted(notes):
            print(f"  {note}")
    if fails:
        print(f"\nFAIL: {len(fails)}")
        for fail in fails[:40]:
            print(f"  {fail}")
        if len(fails) > 40:
            print(f"  ... and {len(fails) - 40} more")
        print(
            "\nNothing is rewritten automatically -- see CLAUDE.md, "
            "'Sensitive content gate'.\nRemove the value, then re-run."
        )
    print("\nRESULT:", "FAIL" if fails else "PASS")
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
