"""Validate the compact Claude skill catalog."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EXPECTED = {
    "delivery-router",
    "planning-work",
    "developing-change",
    "governing-ai-data",
    "verifying-change",
    "releasing-deploying",
    "operating-production",
    "reporting-handoff",
}
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


def words(text: str) -> int:
    return len(text.split())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--allow-legacy", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []
    dirs = {p.name: p for p in ROOT.iterdir() if p.is_dir()}

    missing = EXPECTED - dirs.keys()
    extra = dirs.keys() - EXPECTED
    if missing:
        errors.append("missing: " + ", ".join(sorted(missing)))
    if extra and not args.allow_legacy:
        errors.append("unexpected top-level skills: " + ", ".join(sorted(extra)))

    total_words = 0
    description_words = 0
    for name in sorted(EXPECTED & dirs.keys()):
        entry = dirs[name] / "SKILL.md"
        if not entry.is_file():
            errors.append(f"{name}: missing SKILL.md")
            continue
        text = entry.read_text(encoding="utf-8")
        total_words += words(text)
        if words(text) > 220:
            errors.append(f"{name}: SKILL.md exceeds 220 words")
        if not NAME_RE.fullmatch(name) or f"name: {name}" not in text:
            errors.append(f"{name}: invalid or mismatched name")
        match = re.search(r"^description:\s*(.+)$", text, re.MULTILINE)
        if not match or not match.group(1).startswith("Use when "):
            errors.append(f"{name}: invalid description")
        elif len(match.group(1)) > 240:
            errors.append(f"{name}: description exceeds 240 characters")
        else:
            description_words += words(match.group(1))
        for target in LINK_RE.findall(text):
            if "://" in target or target.startswith("#"):
                continue
            if not (entry.parent / target.split("#", 1)[0]).exists():
                errors.append(f"{name}: broken link {target}")

    if total_words > 1400:
        errors.append(f"top-level SKILL word budget exceeded: {total_words}")
    if description_words > 180:
        errors.append(f"description word budget exceeded: {description_words}")

    if errors:
        print("Catalog validation failed:")
        for error in errors:
            print(f"- {error}")
        return 1
    print(
        f"Catalog validation passed: {len(EXPECTED)} skills, "
        f"{total_words} top-level words, {description_words} description words"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
