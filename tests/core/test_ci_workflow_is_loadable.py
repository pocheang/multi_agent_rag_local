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
"""

from __future__ import annotations

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
