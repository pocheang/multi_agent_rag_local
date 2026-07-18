from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import unquote

EXCLUDED_PARTS = {"archive", "history", "releases", "superpowers"}
FORBIDDEN_TERMS = (
    "docs/guides/",
    "docs/project/",
    "internal_docs/",
    ".env.docker.example",
    "start-all.ps1",
    "start-backend.ps1",
    "start-frontend.ps1",
)
EXPLANATORY_MARKERS = (
    "不存在",
    "如果有",
    "历史",
    "归档",
    "不创建",
    "不再",
    "不发布",
    "内部",
    "not published",
    "now archived",
    "legacy",
)


def current_markdown_files(docs_root: Path) -> list[Path]:
    return [
        path
        for path in docs_root.rglob("*.md")
        if not (set(path.relative_to(docs_root).parts) & EXCLUDED_PARTS)
    ]


def is_external(target: str) -> bool:
    lowered = target.lower()
    return (
        not target
        or target.startswith("#")
        or lowered.startswith(("http://", "https://", "mailto:", "tel:", "data:"))
    )


def link_targets(line: str) -> list[str]:
    targets = []
    cursor = 0
    while True:
        start = line.find("](", cursor)
        if start < 0:
            return targets
        end = line.find(")", start + 2)
        if end < 0:
            return targets
        target = line[start + 2 : end].strip()
        if target.startswith("<") and ">" in target:
            target = target[1 : target.index(">")]
        else:
            parts = target.split(maxsplit=1)
            target = parts[0] if parts else ""
        targets.append(target)
        cursor = end + 1


def local_target(source: Path, target: str) -> Path | None:
    target = unquote(target.split("#", 1)[0])
    if is_external(target):
        return None
    return (source.parent / target).resolve()


def check_links(files: list[Path], repo_root: Path) -> list[str]:
    failures = []
    for source in files:
        in_code = False
        for line_number, line in enumerate(
            source.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            stripped = line.strip()
            if stripped.startswith("~~~") or stripped.startswith(chr(96) * 3):
                in_code = not in_code
                continue
            if in_code:
                continue
            for raw_target in link_targets(line):
                target = local_target(source, raw_target)
                if target is None:
                    continue
                if target.is_file():
                    continue
                if target.is_dir() and (
                    (target / "README.md").is_file() or (target / "INDEX.md").is_file()
                ):
                    continue
                failures.append(
                    f"{source.relative_to(repo_root)}:{line_number} -> {raw_target}"
                )
    return failures


def check_forbidden_paths(files: list[Path], repo_root: Path) -> list[str]:
    failures = []
    for source in files:
        if source.name == "DOCUMENTATION_POLICY.md" or "design" in source.parts:
            continue
        in_code = False
        for line_number, line in enumerate(
            source.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            stripped = line.strip()
            if stripped.startswith("~~~") or stripped.startswith(chr(96) * 3):
                in_code = not in_code
                continue
            if in_code or any(marker in line for marker in EXPLANATORY_MARKERS):
                continue
            if any(term in line for term in FORBIDDEN_TERMS):
                failures.append(f"{source.relative_to(repo_root)}:{line_number}")
    return failures


def check_release_index(repo_root: Path) -> list[str]:
    release_root = repo_root / "docs" / "releases"
    index = release_root / "README.md"
    if not index.is_file():
        return ["docs/releases/README.md is missing"]
    text = index.read_text(encoding="utf-8", errors="replace")
    linked = set()
    for line in text.splitlines():
        if "](" in line and ".md)" in line:
            linked.add(line.split("](", 1)[1].split(")", 1)[0].removeprefix("./"))
    failures = []
    for path in release_root.glob("*.md"):
        name = path.name
        if name == "README.md" or "CORRECTIONS" in name.upper():
            continue
        if "v0." in name and name not in linked:
            failures.append(f"docs/releases/README.md does not link {name}")
    return failures


def main() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    files = current_markdown_files(repo_root / "docs")
    failures = []
    failures.extend(("broken link: " + item) for item in check_links(files, repo_root))
    failures.extend(("forbidden current path: " + item) for item in check_forbidden_paths(files, repo_root))
    failures.extend(("release index: " + item) for item in check_release_index(repo_root))

    print(f"Scanned {len(files)} current Markdown files.")
    if failures:
        print(f"Found {len(failures)} documentation issue(s):")
        for item in failures:
            print(f"- {item}")
        return 1
    print("Documentation integrity checks passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

