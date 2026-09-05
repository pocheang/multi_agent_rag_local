"""`make up` has to actually start Neo4j, and only on the development stack.

Two defects, both invisible until someone ran it.

`make up` was `docker compose up -d neo4j`, with no `-f`. There is no compose
file in the repository root, so it exited with "no configuration file provided"
-- a command documented in CLAUDE.md that could never have worked. The stack
lives under deploy/compose/, compose.yaml declares NEO4J_PASSWORD with `:?` so
it is mandatory, and the relative paths inside those files are written for
deploy/compose/ as the base directory.

And no service published a port. That is right for compose.yaml, which is the
production stack -- containers reach each other over the `querymind` network and
the backend uses `bolt://neo4j:7687`. But a locally run uvicorn is not on that
network: NEO4J_URI defaults to bolt://localhost:7687, so the graph route was
unreachable from the normal development loop and the Neo4j Browser could not be
opened at all.

The fix belongs in the dev overlay, and the tests below pin both halves: the
ports exist in development, and they still do not exist in production.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
BASE = REPO / "deploy" / "compose" / "compose.yaml"
DEV = REPO / "deploy" / "compose" / "compose.dev.yaml"
MAKEFILE = REPO / "Makefile"


def _services(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8")).get("services", {})


def _up_recipe() -> str:
    text = MAKEFILE.read_text(encoding="utf-8")
    body = text.split("\nup:\n", 1)[1].split("\n\n", 1)[0]
    # `make up` expands COMPOSE_DEV, so the assertions below need it inlined.
    compose_dev = re.search(r"^COMPOSE_DEV = (.+)$", text, re.MULTILINE)
    assert compose_dev is not None, "COMPOSE_DEV is gone; update this test"
    return body.replace("$(COMPOSE_DEV)", compose_dev.group(1))


def _compose_file_arguments() -> list[str]:
    r"""The `-f` arguments `docker compose` itself receives.

    Scoped to the compose command line, because the recipe's first line is a
    shell guard -- `@test -f .runtime/development.env || ...` -- whose `-f` is
    test(1)'s file predicate. Matching `-f (\S+)` over the whole recipe swept
    that up, so the assertion below also demanded a **gitignored** runtime file:
    it passed on a machine that had run `make config-render` and failed on every
    fresh clone, CI included.
    """

    lines = [line for line in _up_recipe().splitlines() if "docker compose" in line]
    assert len(lines) == 1, f"expected one compose invocation in `up:`, found {len(lines)}"
    return re.findall(r"-f (\S+)", lines[0])


def test_make_up_names_compose_files_that_exist():
    """The assertion that would have caught it: no -f meant no compose file."""

    referenced = _compose_file_arguments()

    assert referenced, "`make up` passes no -f, so it falls back to a root compose file that does not exist"
    for rel in referenced:
        assert (REPO / rel).is_file(), f"{rel} does not exist"


def test_make_up_only_names_files_that_ship():
    """What the assertion above was accidentally testing, made deliberate and
    correct. A compose file `make up` needs must be tracked -- a path that
    resolves only because the developer generated it is not a working command
    for anybody else."""

    for rel in _compose_file_arguments():
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", rel],
            cwd=REPO,
            capture_output=True,
            text=True,
        )
        assert tracked.returncode == 0, f"{rel} is not tracked by git, so a fresh clone cannot `make up`"


def test_make_up_uses_the_development_overlay():
    """Without the overlay the ports are not published and the command starts a
    Neo4j nothing on the host can reach."""

    assert "compose.dev.yaml" in _up_recipe()


def test_make_up_supplies_the_mandatory_password():
    """compose.yaml declares NEO4J_PASSWORD with `:?`, so compose refuses to
    render without it. `.runtime/development.env` is where it lives."""

    recipe = _up_recipe()

    assert "--env-file" in recipe
    assert ".runtime/development.env" in recipe


def test_make_up_does_not_override_the_compose_base_directory():
    """Relative paths in these files -- `env_file: ../../.runtime/...` and the
    `../../app` bind mounts -- are written for deploy/compose/ as the base.
    Passing --project-directory sends both two levels too high; verified, it
    looked for .runtime/ beside the repository."""

    assert "--project-directory" not in _up_recipe()


@pytest.mark.parametrize("port", ["7474", "7687"])
def test_development_publishes_the_graph_ports(port: str):
    published = _services(DEV).get("neo4j", {}).get("ports", [])

    assert any(port in str(entry) for entry in published), f"port {port} is not published for development"


def test_production_publishes_no_graph_port():
    """The half that keeps the fix from leaking. Neo4j here holds a password
    from .runtime/, and the production stack deliberately publishes nothing."""

    assert "ports" not in _services(BASE).get("neo4j", {})


def test_every_development_port_is_bound_to_loopback():
    """0.0.0.0 would publish these to the local network. Every existing entry in
    this file already binds 127.0.0.1; a new one must too."""

    for name, service in _services(DEV).items():
        for entry in service.get("ports", []) or []:
            assert str(entry).startswith("127.0.0.1:"), f"{name} publishes {entry} beyond loopback"
