"""The CI workflow must parse, and its steps must survive parsing intact.

A workflow file GitHub cannot read does not report a syntax error. The run
appears in the list as `failure`, named after the file path rather than the
workflow, with zero jobs -- which reads exactly like a test failure until you
open it. Every check the repository has can be green while nothing runs.

That happened on 2026-09-02, adding `--only-binary :all:` to the pip steps:

    run: pip install --only-binary :all: "ruff==0.16.5"

The `: ` inside a plain scalar makes YAML read the rest as a mapping. The value
had to be quoted. Nothing in the repository could have caught it, because the
only consumer of this file is GitHub.

The second assertion is the one worth keeping past that fix. Quoting is easy to
get wrong in the other direction too -- a value that parses but arrives at the
shell with quotes still attached, or a folded scalar that eats a line break --
so the test reads the parsed step back and checks the command is what was meant,
rather than only that the document loads.

The third assertion came from the same file on 2026-09-03, one commit later: a
scanner step added as `SonarSource/sonarqube-scan-action@v8` turned the quality
gate red (`githubactions:S7637`). Nothing local could see it -- the rule lives in
SonarCloud and only runs after a push -- which is exactly the gap this file
exists to close.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

yaml = pytest.importorskip("yaml")

WORKFLOWS = sorted((Path(__file__).resolve().parents[2] / ".github" / "workflows").glob("*.yml"))


def test_there_is_at_least_one_workflow() -> None:
    """Otherwise the parametrised test below passes by having nothing to do."""

    assert WORKFLOWS


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_the_workflow_parses(path: Path) -> None:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))

    assert isinstance(document, dict), f"{path.name} did not parse as a mapping"
    assert document.get("jobs"), f"{path.name} declares no jobs"


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_every_run_step_survives_parsing(path: Path) -> None:
    document = yaml.safe_load(path.read_text(encoding="utf-8"))

    for job_name, job in document["jobs"].items():
        for step in job.get("steps", []):
            command = step.get("run")
            if command is None:
                continue
            assert command.strip(), f"{path.name}:{job_name} has an empty run step"
            assert not command.lstrip().startswith(("'", '"')), (
                f"{path.name}:{job_name} run step still carries its quotes after parsing, "
                f"so the shell would receive them: {command[:60]!r}"
            )


# GitHub's own actions are exempt: the rule this guard mirrors flags third-party
# ones, and pinning `actions/checkout` to a commit costs more than it buys --
# nobody else can move a tag in that namespace.
TRUSTED_ACTION_OWNERS = frozenset({"actions", "github"})

_SHA = re.compile(r"^[0-9a-f]{40}$")


def _action_references(document: dict) -> list[tuple[str, str]]:
    """(job name, `uses` value) for every step that runs somebody's action."""

    found: list[tuple[str, str]] = []
    for job_name, job in document["jobs"].items():
        for step in job.get("steps", []):
            uses = step.get("uses")
            if isinstance(uses, str) and uses.strip():
                found.append((job_name, uses.strip()))
    return found


@pytest.mark.parametrize("path", WORKFLOWS, ids=lambda p: p.name)
def test_third_party_actions_are_pinned_to_a_commit(path: Path) -> None:
    """A tag on somebody else's repository can be moved to different code.

    These steps run with the workflow's secrets. "Whatever v8 points at today"
    is not something to hand a token to, and the repository already applies the
    same reasoning to its Python dependencies -- installed from a lock with every
    archive hashed, rather than from a range.
    """

    unpinned = []
    for job_name, uses in _action_references(yaml.safe_load(path.read_text(encoding="utf-8"))):
        owner = uses.split("/", 1)[0].lower()
        if owner in TRUSTED_ACTION_OWNERS or uses.startswith(("./", "docker://")):
            continue
        reference = uses.rsplit("@", 1)[-1] if "@" in uses else ""
        if not _SHA.match(reference):
            unpinned.append(f"{job_name}: {uses}")

    assert not unpinned, (
        f"{path.name} uses third-party actions by tag rather than by commit: {unpinned}. "
        "Pin the full 40-character SHA and put the version in a comment beside it."
    )
