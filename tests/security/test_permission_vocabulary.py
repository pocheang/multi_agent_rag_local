"""The permission a route checks must be one a role can hold.

Permissions were string literals in two places with nothing tying them together:
granted in `rbac._ROLE_ACTIONS`, and checked at a hundred-odd `_require_permission`
call sites. A divergence between the two fails *closed* -- the check never
matches -- so a role loses a capability silently and the only symptom is a 403
nobody can account for. Nothing in the repository could have detected that.

`Permission` is the vocabulary now, and this is what keeps the two sides using
it. The interesting assertions are the two exception lists: a permission checked
but granted to no role, and a permission granted but checked by nothing. Both
are legitimate in small numbers -- admin holds "*", and three aliases are kept
for backward compatibility -- so they are enumerated rather than forbidden, and
the test fails when the set changes rather than when it is non-empty.

That last part is the point. `session:lock_strategy`, `document:delete_own` and
`document:reindex_own` are granted and asked for by nothing, which is either a
check that was never written or a grant that outlived one. Recording them is not
endorsing them; it is making the next addition to that list deliberate.
"""

from __future__ import annotations

import ast
from pathlib import Path

from app.services.security.rbac import _ROLE_ACTIONS, ADMIN_ONLY, ALL_ROLES, UNCHECKED_GRANTS, Permission

APP = Path(__file__).resolve().parents[2] / "app"

_CHECKERS = {"_require_permission", "can", "require_permission"}


def _checked_permissions() -> set[str]:
    """Every permission string passed to a permission check anywhere in app/."""

    found: set[str] = set()
    for path in APP.rglob("*.py"):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError:  # pragma: no cover - a parse failure is another test's job
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", None) or getattr(node.func, "attr", None)
            if name not in _CHECKERS:
                continue
            for arg in node.args:
                if isinstance(arg, ast.Constant) and isinstance(arg.value, str) and ":" in arg.value:
                    found.add(arg.value)
                elif isinstance(arg, ast.Attribute) and getattr(arg.value, "id", None) == "Permission":
                    found.add(str(getattr(Permission, arg.attr)))
    return found


def _granted_permissions() -> set[str]:
    return {str(action) for actions in _ROLE_ACTIONS.values() for action in actions} - {ALL_ROLES}


class TestTheTwoSidesShareOneVocabulary:
    def test_every_granted_permission_is_declared(self) -> None:
        undeclared = _granted_permissions() - {str(p) for p in Permission}

        assert not undeclared, f"granted but not in Permission: {sorted(undeclared)}"

    def test_every_checked_permission_is_declared(self) -> None:
        undeclared = _checked_permissions() - {str(p) for p in Permission}

        assert not undeclared, f"checked but not in Permission: {sorted(undeclared)}"

    def test_a_checked_permission_is_either_grantable_or_admin_only(self) -> None:
        """The failure this exists for: a check no role can ever satisfy."""

        unreachable = _checked_permissions() - _granted_permissions() - set(ADMIN_ONLY)

        assert not unreachable, (
            f"these are checked but granted to no role, and are not listed as admin-only: {sorted(unreachable)}. "
            "Either grant them, or add them to ADMIN_ONLY."
        )

    def test_the_set_of_unchecked_grants_has_not_grown(self) -> None:
        """A grant nothing asks for is dead weight at best and a missing check at
        worst. The list is frozen so adding to it has to be deliberate."""

        unchecked = _granted_permissions() - _checked_permissions()

        assert unchecked == set(UNCHECKED_GRANTS), (
            f"unexpected: {sorted(unchecked - set(UNCHECKED_GRANTS))}, "
            f"no longer unchecked: {sorted(set(UNCHECKED_GRANTS) - unchecked)}"
        )


class TestTheGrantsThemselves:
    def test_admin_holds_everything(self) -> None:
        assert _ROLE_ACTIONS["admin"] == {ALL_ROLES}

    def test_no_role_but_admin_holds_an_admin_permission(self) -> None:
        for role, actions in _ROLE_ACTIONS.items():
            if role == "admin":
                continue
            assert not ({str(a) for a in actions} & set(ADMIN_ONLY)), f"{role} holds an admin permission"

    def test_analyst_and_viewer_differ_only_where_intended(self) -> None:
        """They were written out separately, which hid how nearly identical they
        are; the shared set is now explicit and this pins the difference."""

        analyst = {str(a) for a in _ROLE_ACTIONS["analyst"]}
        viewer = {str(a) for a in _ROLE_ACTIONS["viewer"]}

        assert analyst - viewer == {Permission.SESSION_MANAGE, Permission.MESSAGE_MANAGE}
        assert viewer - analyst == {Permission.SESSION_UPDATE}
