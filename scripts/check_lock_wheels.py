"""List the locked packages that publish no wheel for the target platform.

`--only-binary :all:` refuses source distributions, which is what keeps a
`setup.py` from running during an install. A package that publishes no wheel at
all therefore cannot be installed under it and has to be named in
`--no-binary`, one exemption at a time.

Finding those one at a time is what this exists to stop. Two of them broke CI on
consecutive pushes -- jieba first, then forbiddenfruit (a dependency of
blockbuster) -- each discovered only by a red build, because the failure is a
property of PyPI rather than of anything in the repository. Asking PyPI for the
whole lock at once takes about twenty seconds.

Run it after `make lock`; `make lock` does. It queries PyPI, so it is not part of
the test suite: a unit test that needs the network fails on a train.

    python scripts/check_lock_wheels.py

It takes no arguments on purpose. The two locks are the only thing it has to
read, and a path off the command line is a path this script would then open --
which is what `pythonsecurity:S8707` said about its first version, correctly.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from packaging.markers import Marker
from packaging.tags import Tag
from packaging.utils import parse_wheel_filename

# The platform CI and the image run on, and the one the locks are compiled for.
TARGET_MINOR = 11

_PINNED = re.compile(
    # Every quantifier is bounded and none of them may cross a line: `\s`
    # matches a newline, and under re.M that let `\s*;\s*` reach past the
    # end of one requirement into the next line (python:S8786).
    r"^([A-Za-z0-9][A-Za-z0-9._-]*)==([^\s;]+)(?:[ \t]{0,8};[ \t]{0,8}(?P<marker>[^\n]*?))?[ \t]{0,8}\\?$",
    re.M,
)
_CPYTHON = re.compile(r"^cp3(\d+)$")

ROOT = Path(__file__).resolve().parents[1]
LOCKS = (ROOT / "requirements" / "ci.txt", ROOT / "requirements" / "runtime.txt")

# The exports are universal -- one entry per package *per environment* -- so a
# package appears more than once with different versions and different markers,
# and the answer to "does this have a wheel" depends on which one linux/cp311
# would install. Reading them without markers reported numpy, scipy and pywin32
# as wheel-less: the first two because the last line won was the 3.12 pin, the
# third because it is Windows-only and never installed here at all.
INSTALL_ENVIRONMENT = {
    "python_version": "3.11",
    "python_full_version": "3.11.13",
    "sys_platform": "linux",
    "platform_system": "Linux",
    "platform_machine": "x86_64",
    "os_name": "posix",
    "implementation_name": "cpython",
    "platform_python_implementation": "CPython",
    "extra": "",
}


def _platform_ok(platform: str) -> bool:
    if platform == "any":
        return True
    return ("manylinux" in platform or "musllinux" in platform) and "x86_64" in platform


def _usable(tag: Tag) -> bool:
    """Whether cp311 on linux/x86_64 can install a wheel carrying this tag.

    The abi3 case is the one worth spelling out: a stable-ABI wheel names the
    *lowest* interpreter it supports, so `cp39-abi3-manylinux...` installs
    happily on 3.11. Matching the interpreter exactly reports bcrypt, chromadb,
    tokenizers and five others as wheel-less, which is how this function was
    wrong the first time it was written.
    """

    if not _platform_ok(tag.platform):
        return False
    if tag.abi == "abi3":
        match = _CPYTHON.match(tag.interpreter)
        return bool(match) and int(match.group(1)) <= TARGET_MINOR
    if tag.abi == "none":
        return tag.interpreter in {"py3", f"py3{TARGET_MINOR}", f"cp3{TARGET_MINOR}"}
    return tag.abi == f"cp3{TARGET_MINOR}" and tag.interpreter == f"cp3{TARGET_MINOR}"


def _has_usable_wheel(name: str, version: str) -> bool | None:
    """None means PyPI could not be asked, which is not the same as 'no wheel'."""

    url = f"https://pypi.org/pypi/{name}/{version}/json"
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            files = json.load(response)["urls"]
    except Exception as exc:  # noqa: BLE001 -- reported, not swallowed
        print(f"  ? {name}=={version}: could not ask PyPI ({exc})", file=sys.stderr)
        return None
    for entry in files:
        if entry["packagetype"] != "bdist_wheel":
            continue
        try:
            _, _, _, tags = parse_wheel_filename(entry["filename"])
        except Exception:  # noqa: BLE001 -- an unparseable name is not a usable wheel
            continue
        if any(_usable(tag) for tag in tags):
            return True
    return False


def _installed_here(lock: Path) -> dict[str, str]:
    """The pins linux/cp311 would actually install, markers evaluated."""

    pinned: dict[str, str] = {}
    for match in _PINNED.finditer(lock.read_text(encoding="utf-8")):
        name, version, marker = match.group(1), match.group(2), match.group("marker")
        if marker and not Marker(marker).evaluate(INSTALL_ENVIRONMENT):
            continue
        pinned[name] = version
    return pinned


def main() -> int:
    pinned: dict[str, str] = {}
    for lock in LOCKS:
        pinned.update(_installed_here(lock))

    print(f"checking {len(pinned)} locked packages against PyPI for linux/cp311")
    with ThreadPoolExecutor(max_workers=16) as pool:
        results = list(pool.map(lambda item: (item[0], _has_usable_wheel(*item)), sorted(pinned.items())))

    sdist_only = sorted(name for name, ok in results if ok is False)
    unknown = sorted(name for name, ok in results if ok is None)

    if sdist_only:
        print("\nno wheel for linux/cp311 -- each must appear in --no-binary:")
        for name in sdist_only:
            print(f"  {name}")
        print(f"\n  --no-binary {','.join(sdist_only)}")
    else:
        print("\nevery locked package has a wheel; --only-binary :all: needs no exemption")

    if unknown:
        print(f"\ncould not be checked (network): {', '.join(unknown)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
