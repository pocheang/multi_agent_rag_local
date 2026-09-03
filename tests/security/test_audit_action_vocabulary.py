"""The audit log's action names have one definition, and both ends use it.

Three lists had to agree and nothing checked that they did: the writers in
``app/api``, the operations counters in ``app/services/runtime/runtime_ops.py``,
and the admin console's filter dropdown.  Two had already drifted -- the console
offered ``admin.user.password_reset`` against a backend that writes
``admin.user.reset_password``, and the SLO counted an action nothing has ever
written.  Both failures are silent: a filter or a counter that matches no row
reports "nothing happened", which is exactly what a quiet week looks like.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from app.services.security.audit_actions import AuditAction

_REPO = Path(__file__).resolve().parents[2]
_APP = _REPO / "app"
_DEFINITION = _APP / "services" / "security" / "audit_actions.py"
_CONSOLE_OPTIONS = _REPO / "frontend" / "src" / "pages" / "admin" / "constants.ts"

_VALUES = {action.value for action in AuditAction}


def _python_sources() -> list[Path]:
    return [p for p in _APP.rglob("*.py") if "__pycache__" not in p.parts and p != _DEFINITION]


def _string_literals(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return {node.value for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}


@pytest.mark.parametrize("path", _python_sources(), ids=lambda p: str(p.relative_to(_REPO)))
def test_no_module_spells_an_audit_action_by_hand(path: Path) -> None:
    """Writers and readers both go through AuditAction, so a typo cannot compile."""

    spelled = _string_literals(path) & _VALUES
    assert not spelled, (
        f"{path.relative_to(_REPO)} writes audit action names as literals: {sorted(spelled)}. "
        "Use AuditAction so the writing end and the reading end cannot drift apart."
    )


def test_the_console_filter_offers_actions_that_exist() -> None:
    """Every option in the admin console's dropdown must match rows the app writes."""

    source = _CONSOLE_OPTIONS.read_text(encoding="utf-8")
    block = re.search(r"ACTION_KEYWORD_OPTIONS = \[(.*?)\]", source, re.DOTALL)
    assert block, f"{_CONSOLE_OPTIONS.name} no longer declares ACTION_KEYWORD_OPTIONS"

    offered = set(re.findall(r'"([^"]+)"', block.group(1)))
    assert offered, "the console offers no actions at all"

    unknown = offered - _VALUES
    assert not unknown, (
        f"the admin console filters on audit actions nothing writes: {sorted(unknown)}. "
        "The backend filter is a substring match, so these options can only ever return nothing."
    )


def test_the_vocabulary_is_only_declared_once() -> None:
    """A second copy of the list is how the first divergence happened."""

    duplicates = [
        p.relative_to(_REPO)
        for p in (_REPO / "frontend" / "src").rglob("*.ts*")
        if p != _CONSOLE_OPTIONS and "ACTION_KEYWORD_OPTIONS = [" in p.read_text(encoding="utf-8")
    ]
    assert not duplicates, f"the console's action list is declared again in: {duplicates}"
