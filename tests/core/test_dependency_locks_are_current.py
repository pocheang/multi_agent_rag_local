"""The locks must still describe pyproject.toml.

`requirements/runtime.txt` and `requirements/ci.txt` are what CI and the image
install from, so a dependency added to pyproject.toml and not compiled into them
is not installed at all -- and the failure surfaces as an ImportError in an
unrelated test, which is a long way from its cause.

Regenerating takes minutes (the hashes are computed from the real archives), so
it will be forgotten. This is the thing that says so at the point of the change.

What it does *not* check is that the pinned versions are the ones a fresh
resolution would produce today; answering that means re-resolving, which is the
ten-minute job itself. The claim here is narrower and is the one that catches the
mistake people actually make: every direct requirement appears, at a version its
own specifier accepts.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

packaging_requirements = pytest.importorskip("packaging.requirements")
packaging_markers = pytest.importorskip("packaging.markers")

ROOT = Path(__file__).resolve().parents[2]
LOCKS = {
    "runtime.txt": [],  # project dependencies only
    "ci.txt": ["dev"],  # plus the dev extra, which is what CI installs
}

# The environment the locks were compiled for: `uv pip compile --python-platform
# linux --python-version 3.11`, matching the CI runner and the base image.
LOCK_ENVIRONMENT = {
    "python_version": "3.11",
    "python_full_version": "3.11.0",
    "sys_platform": "linux",
    "platform_system": "Linux",
    "platform_machine": "x86_64",
    "os_name": "posix",
    "implementation_name": "cpython",
    "platform_python_implementation": "CPython",
}

_PINNED = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)==(\S+?)(?:\s|\\|$)")


def _normalise(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _locked_versions(lock: Path) -> dict[str, str]:
    found = {}
    for line in lock.read_text(encoding="utf-8").splitlines():
        match = _PINNED.match(line)
        if match:
            found[_normalise(match.group(1))] = match.group(2)
    return found


def _direct_requirements(extras: list[str]) -> list[str]:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    requirements = list(project["dependencies"])
    for extra in extras:
        requirements += list(project["optional-dependencies"][extra])
    return requirements


@pytest.mark.parametrize("lock_name", sorted(LOCKS))
def test_the_lock_exists_and_pins_everything_it_lists(lock_name: str) -> None:
    lock = ROOT / "requirements" / lock_name

    assert lock.is_file(), f"{lock_name} is missing; run `make lock`"

    unpinned = [
        line
        for line in lock.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith(("#", " ", "\t", "--")) and "==" not in line
    ]
    assert not unpinned, f"{lock_name} carries unpinned entries: {unpinned[:5]}"


@pytest.mark.parametrize("lock_name", sorted(LOCKS))
def test_every_direct_dependency_is_locked(lock_name: str) -> None:
    locked = _locked_versions(ROOT / "requirements" / lock_name)
    missing: list[str] = []
    unsatisfied: list[str] = []

    for raw in _direct_requirements(LOCKS[lock_name]):
        requirement = packaging_requirements.Requirement(raw)
        if requirement.marker and not requirement.marker.evaluate(LOCK_ENVIRONMENT):
            continue  # not installed on the platform the lock was compiled for
        version = locked.get(_normalise(requirement.name))
        if version is None:
            missing.append(requirement.name)
        elif not requirement.specifier.contains(version, prereleases=True):
            unsatisfied.append(f"{requirement.name}{requirement.specifier} is locked at {version}")

    assert not missing, f"not in requirements/{lock_name}: {missing}. Run `make lock`."
    assert not unsatisfied, f"requirements/{lock_name} contradicts pyproject.toml: {unsatisfied}. Run `make lock`."


def test_the_ci_lock_is_a_superset_of_the_runtime_lock() -> None:
    """They are compiled separately, so they can drift into disagreeing about a
    shared transitive dependency -- which would mean CI testing one version and
    the image shipping another."""

    runtime = _locked_versions(ROOT / "requirements" / "runtime.txt")
    ci = _locked_versions(ROOT / "requirements" / "ci.txt")

    disagreements = [
        f"{name}: runtime {version} vs ci {ci[name]}"
        for name, version in runtime.items()
        if name in ci and ci[name] != version
    ]
    missing = sorted(set(runtime) - set(ci))

    assert not missing, f"in the runtime lock but not the ci lock: {missing}"
    assert not disagreements, f"the two locks disagree: {disagreements}"
