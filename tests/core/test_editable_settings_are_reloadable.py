"""An admin-editable field must not be read through a frozen Settings object.

CLAUDE.md makes an audited claim: `requires_restart` is False on every editable
field, because "each consumer either reads `get_settings()` per use, or is held
by an object `RAGPipeline` builds per request, or is rebuilt by the reload".

There is a third shape it does not cover. Six modules bind
`settings = get_settings()` at *module scope*. `get_settings` is `lru_cache`d and
a reload calls `cache_clear()`, which builds a **new** object -- so those modules
keep the one they captured at import, for the life of the process.

Nothing is broken today: none of the editable fields is read through one of them,
which is why this file asserts rather than ratchets. But the claim holds by
coincidence, not by construction. Adding a field to `config_schema.py` that
happens to be read in one of those modules would break it silently, and silently
is the whole problem: `POST /admin/config/values` would report success, the
console would show the new value, and the running process would keep the old one
until restart.

That failure mode is already documented once, for `CASCADE_*` and the module
global `_get_validation_cascade` caches. This is the same hazard reached from a
different direction, so it gets a guard rather than a paragraph.

Both sides are discovered, not listed: a seventh frozen module or a thirtieth
editable field is covered the day it is added.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONFIG = REPO / "app" / "core" / "config.py"
SCHEMA = REPO / "app" / "core" / "config_schema.py"


def _editable_fields() -> dict[str, str]:
    """Admin-editable aliases mapped to their Settings attribute names."""

    aliases = set(re.findall(r'EditableField\(\s*"([A-Z0-9_]+)"', SCHEMA.read_text(encoding="utf-8")))
    declared = re.findall(
        r'^\s*(\w+)\s*:.*alias="([A-Z0-9_]+)"',
        CONFIG.read_text(encoding="utf-8"),
        re.MULTILINE,
    )
    return {field: alias for field, alias in declared if alias in aliases}


def _modules_that_freeze_settings() -> list[Path]:
    """Modules binding `settings = get_settings()` at module scope."""

    frozen: list[Path] = []
    for path in sorted((REPO / "app").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except SyntaxError:  # pragma: no cover - not expected in first-party code
            continue
        for node in tree.body:  # module scope only
            if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call):
                continue
            call = node.value.func
            name = call.id if isinstance(call, ast.Name) else getattr(call, "attr", "")
            if name == "get_settings" and any(
                isinstance(target, ast.Name) and target.id == "settings" for target in node.targets
            ):
                frozen.append(path)
                break
    return frozen


def test_some_modules_do_freeze_settings():
    """Guards the guard: if this stops finding any, the test below is vacuous and
    the assertion that matters would pass for the wrong reason."""

    assert _modules_that_freeze_settings(), "no module binds settings at import; this file's premise is stale"


def test_editable_fields_are_all_declared_in_settings():
    """A `config_schema.py` alias that matches no field is a knob the console
    offers and nothing implements."""

    aliases = set(re.findall(r'EditableField\(\s*"([A-Z0-9_]+)"', SCHEMA.read_text(encoding="utf-8")))
    resolved = set(_editable_fields().values())

    assert aliases == resolved, f"editable aliases with no Settings field: {sorted(aliases - resolved)}"


def test_no_editable_field_is_read_through_a_frozen_settings_object():
    """The claim CLAUDE.md audits, enforced instead of re-audited.

    A hit here does not mean "delete the field". It means that field cannot
    honestly carry `requires_restart=False` until its reader stops holding an
    import-time Settings -- so either the reader switches to `get_settings()` per
    use, or the field leaves the editable allowlist.
    """

    editable = _editable_fields()
    offenders: list[str] = []

    for path in _modules_that_freeze_settings():
        text = path.read_text(encoding="utf-8", errors="ignore")
        for field, alias in editable.items():
            # Both spellings: settings.field, and getattr(settings, "field", ...)
            direct = rf"\bsettings\.{re.escape(field)}\b"
            indirect = rf'getattr\(\s*settings\s*,\s*"{re.escape(field)}"'
            if re.search(direct, text) or re.search(indirect, text):
                offenders.append(f"{path.relative_to(REPO).as_posix()} reads {alias} ({field})")

    assert not offenders, (
        "these admin-editable settings are read from a Settings frozen at import, "
        "so a console edit would report success and change nothing until restart:\n  " + "\n  ".join(sorted(offenders))
    )


# --- the reload must reach the caches built from Settings --------------------


def test_reloading_rebuilds_the_validation_cascade():
    """`_get_validation_cascade` caches a module global that bakes in every
    CASCADE_* value at construction, and the NLI model is lru_cache'd on
    NLI_MODEL_NAME. Nothing else rebuilds either, so before this a reload changed
    the numbers the admin page reports and nothing the cascade runs on.

    That is why CASCADE_* was kept out of config_schema.py; clearing these is the
    prerequisite for that decision being reconsidered on its own merits rather
    than blocked by a stale cache.
    """

    from app.agents.validation import public

    first = public._get_validation_cascade()
    assert public._get_validation_cascade() is first, "the cascade is supposed to be cached"

    public.clear_validation_caches()

    assert public._get_validation_cascade() is not first


def test_the_reload_sequence_clears_the_validation_caches():
    """The admin endpoint and the configuration-centre watcher share one
    definition of "reloaded"; a cache cleared by only one of them would be a
    second, quieter definition."""

    source = (REPO / "app" / "api" / "application" / "config_reload.py").read_text(encoding="utf-8")
    sequence = source.split("def apply_config_reload(", 1)[1].split("\ndef ", 1)[0]

    assert "clear_validation_caches()" in sequence


def test_the_reload_empties_the_router_decision_memo():
    """A cached route outlives the setting that produced it, unless cleared.

    `decide_route` is memoized for 30 minutes on a key of question and hints
    only, and its result reads two editable settings -- ENABLE_CALIBRATION via
    `_calibrated`, and ENABLE_WEB_ROUTE_DOWNGRADE via `_llm_route`. Until
    2026-09-06 the reload did not clear it, so toggling either from the admin
    console returned success and left every question already in the cache routing
    the old way until its entry expired: the reranker-lru_cache defect again, in
    a store the guard below cannot see because it is hand-rolled rather than
    `@lru_cache`.

    Two halves, because neither alone is the property. The clearer has to empty
    the store, and the shared reload sequence has to call it -- a clearer that
    works and is only called by the admin endpoint is the "second, quieter
    definition of reloaded" its sibling above is about.
    """

    from app.agents.shared import cache as router_cache

    router_cache._router_decision_cache.set("some-cached-route", "vector")
    assert router_cache._router_decision_cache.get("some-cached-route") == "vector"
    router_cache.clear_router_decision_cache()
    assert router_cache._router_decision_cache.get("some-cached-route") is None

    source = (REPO / "app" / "api" / "application" / "config_reload.py").read_text(encoding="utf-8")
    sequence = source.split("def apply_config_reload(", 1)[1].split("\ndef ", 1)[0]
    assert "clear_router_decision_cache()" in sequence


# --- an editable field behind an lru_cache must be cleared by the reload ------


def _lru_cached_functions() -> dict[str, tuple[Path, str]]:
    """`@lru_cache` functions in app/, mapped to their file and source."""

    found: dict[str, tuple[Path, str]] = {}
    for path in sorted((REPO / "app").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        try:
            tree = ast.parse(text)
        except SyntaxError:  # pragma: no cover
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef):
                continue
            for decorator in node.decorator_list:
                target = decorator.func if isinstance(decorator, ast.Call) else decorator
                name = getattr(target, "id", None) or getattr(target, "attr", None)
                if name == "lru_cache":
                    found[node.name] = (path, ast.get_source_segment(text, node) or "")
    return found


def _names_cleared_by_the_reload() -> set[str]:
    """Every `X.cache_clear()` the reload reaches, one level of indirection deep.

    `apply_config_reload` mostly calls small named clearers -- clear_model_caches,
    clear_reranker_cache, clear_validation_caches -- rather than clearing caches
    itself, so following the calls it makes is the difference between this guard
    working and it only recognising the one style.
    """

    reload_src = (REPO / "app" / "api" / "application" / "config_reload.py").read_text(encoding="utf-8")
    sequence = reload_src.split("def apply_config_reload(", 1)[1].split("\ndef ", 1)[0]
    called = set(re.findall(r"\b(\w+)\(", sequence))

    cleared: set[str] = set(re.findall(r"(\w+)\.cache_clear\(\)", sequence))
    for path in sorted((REPO / "app").rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        for name in called:
            match = re.search(rf"^def {re.escape(name)}\(.*?(?=^\S|\Z)", text, re.MULTILINE | re.DOTALL)
            if match:
                cleared.update(re.findall(r"(\w+)\.cache_clear\(\)", match.group(0)))
    return cleared


def test_the_reload_reaches_every_cache_that_holds_an_editable_setting():
    """The guard for the shape that nearly shipped.

    RERANKER_MODEL_NAME is read inside `_load_cross_encoder`, an lru_cache'd
    loader that `clear_model_caches` does not touch -- it covers the chat and
    embedding models only. Offering the field without clearing that cache would
    have let the page report a model the process had not loaded, which is the
    same silent inertness the module-scope `settings` binding causes above,
    reached through a different mechanism.
    """

    editable = set(_editable_fields())
    cleared = _names_cleared_by_the_reload()
    offenders: list[str] = []

    for name, (path, source) in _lru_cached_functions().items():
        held = sorted(
            field
            for field in editable
            if re.search(rf"\bsettings\.{re.escape(field)}\b", source)
            or re.search(rf'getattr\(\s*settings\s*,\s*"{re.escape(field)}"', source)
        )
        if held and name not in cleared:
            offenders.append(f"{path.relative_to(REPO).as_posix()}::{name} holds {', '.join(held)}")

    assert not offenders, (
        "these lru_cache'd functions read an admin-editable setting and the reload never "
        "clears them, so an edit would report success and change nothing until restart:\n  "
        + "\n  ".join(sorted(offenders))
    )
