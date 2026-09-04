"""The gate that decides what may leave this machine has to be able to fail.

`scripts/check_sensitive.py` runs in pre-commit and in CI, and its output on a
healthy repository is PASS. That is also its output when it is broken, which is
the whole problem with this class of tool: a scanner whose checks silently match
nothing reports exactly what a clean repository reports, forever.

That is not hypothetical. The first draft of that script was patched to drop a
false positive and the edit reduced `\\\\+` to `\\+` inside the local-path
pattern -- a literal plus sign -- so no Windows user-profile path could match
any more. Every run stayed green and the report looked entirely normal. Two
further defects came out of the same exercise: `re.I` made `/Users/[a-z]+/`
match the `/admin/users/<id>/` routes in this very suite, and `/home/[a-z]+/`
could not tell a developer's home directory from a container volume mount.

So the assertions below are mostly negative: each check class is pointed at
input that must trip it. The one positive assertion -- that this repository
passes -- is what turns a newly committed secret into a red test rather than a
red build ten minutes later.

See CLAUDE.md, "Sensitive content gate".
"""

from __future__ import annotations

import importlib.util
import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "check_sensitive.py"


def _load():
    spec = importlib.util.spec_from_file_location("check_sensitive", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


gate = _load()


@pytest.fixture
def scratch() -> Iterator[Path]:
    """A throwaway directory, deliberately not pytest's `scratch`.

    `scratch` builds its trees under a shared per-user basetemp root
    (`.../Temp/pytest-of-<user>`), and creating that root needs directory
    permissions that are not available on every Windows checkout -- every test
    in this file errored with `PermissionError: [WinError 5]` before the whole
    suite even started.

    That mattered more here than it would elsewhere: this file's entire job is to
    prove the sensitive-content gate is *able to fail*, and a suite that cannot
    run proves that no better than a scanner whose checks match nothing. The
    surrounding suites already avoid `scratch` for this reason -- see
    tests/services/test_benchmark_query_set.py.
    """

    root = Path(tempfile.mkdtemp(prefix="querymind-gate-"))
    try:
        yield root
    finally:
        shutil.rmtree(root, ignore_errors=True)


def _scan(root: Path, rels: list[str], whole: bool = False) -> list[str]:
    fails, _ = gate.scan(root, rels, None, whole)
    return fails


def _write(root: Path, rel: str, text: str) -> str:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return rel


# --- each check class must trip -------------------------------------------


def test_a_forced_database_is_caught(scratch: Path) -> None:
    """`git add -f data/app.db` is how a database reaches a repository."""
    rel = _write(scratch, "data/app.db", "")
    kinds = {f.split("]")[0] + "]" for f in _scan(scratch, [rel])}
    assert "[path]" in kinds, "a tracked file under data/ must fail"
    assert "[type]" in kinds, "a .db suffix must fail on its own"


def test_an_env_file_with_a_value_is_caught(scratch: Path) -> None:
    rel = _write(
        scratch,
        ".runtime/generated-secrets.env",
        "# a comment\nEMPTY=\nJWT_SECRET_KEY=abcdef0123456789\n",
    )
    fails = [f for f in _scan(scratch, [rel]) if f.startswith("[env]")]
    assert len(fails) == 1, "only the line carrying a value should fail"
    assert "JWT_SECRET_KEY" in fails[0]
    assert "abcdef0123456789" not in fails[0], "the report must never echo the value"


def test_an_example_env_file_is_exempt(scratch: Path) -> None:
    """A committed .env.example is documentation, and its keys are empty."""
    rel = _write(scratch, ".env.example", "OPENAI_API_KEY=\n")
    assert not [f for f in _scan(scratch, [rel]) if f.startswith("[env]")]


@pytest.mark.parametrize(
    "secret",
    [
        "sk-proj-" + "a" * 24,
        "AKIA" + "B" * 16,
        "ghp_" + "c" * 24,
        "-----BEGIN RSA PRIVATE KEY-----",
    ],
)
def test_credential_shapes_are_caught(scratch: Path, secret: str) -> None:
    rel = _write(scratch, "src/leak.py", f'KEY = "{secret}"\n')
    assert [f for f in _scan(scratch, [rel]) if f.startswith("[secret]")]


def test_a_windows_user_profile_path_is_caught(scratch: Path) -> None:
    """The regression that made this whole file worth having."""
    rel = _write(scratch, "doc.md", "run it from C:" + chr(92) + "Users" + chr(92) + "dev\n")
    assert [f for f in _scan(scratch, [rel]) if f.startswith("[local-path]")]


def test_an_api_route_is_not_a_local_path(scratch: Path) -> None:
    """`re.I` on the path pattern turned every admin route into a finding."""
    rel = _write(scratch, "routes.py", 'PATHS = ["/admin/users/u-1/role", "/api/v1/users/me"]\n')
    assert not [f for f in _scan(scratch, [rel]) if f.startswith("[local-path]")]


def test_a_container_volume_is_not_a_local_path(scratch: Path) -> None:
    rel = _write(scratch, "compose.yaml", "    volumes:\n      - nacos_data:/home/nacos/data\n")
    assert not [f for f in _scan(scratch, [rel]) if f.startswith("[local-path]")]


# --- the baselines are ratchets, not allowlists ---------------------------


def test_a_baseline_entry_that_matches_nothing_fails(scratch: Path, monkeypatch) -> None:
    """An exemption list nobody prunes stops describing anything."""
    rel = _write(scratch, "clean.py", "x = 1\n")
    monkeypatch.setattr(gate, "SECRET_BASELINE", {"gone.py"})
    monkeypatch.setattr(gate, "LOCAL_PATH_BASELINE", set())
    fails = _scan(scratch, [rel], whole=True)
    assert any(f.startswith("[stale baseline]") for f in fails)


def test_the_stale_check_is_off_for_a_partial_scan(scratch: Path) -> None:
    """pre-commit sees a handful of staged files; almost every entry is unused."""
    rel = _write(scratch, "clean.py", "x = 1\n")
    assert not [f for f in _scan(scratch, [rel]) if f.startswith("[stale baseline]")]


def test_the_baselines_name_files_that_exist() -> None:
    for rel in gate.SECRET_BASELINE | gate.LOCAL_PATH_BASELINE:
        assert (REPO / rel).is_file(), f"baseline names a missing file: {rel}"


# --- and the repository itself must pass ----------------------------------


def test_this_repository_passes() -> None:
    rels = gate.tracked_files(REPO)
    fails, _ = gate.scan(REPO, rels, None, True)
    assert not fails, "sensitive content in tracked files:\n  " + "\n  ".join(fails)
