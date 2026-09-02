"""The last three `pythonsecurity:S5145` sites, and what reading them found.

The rule says caller-controlled data reaches a logging call. Reading the three:

- `guard.py` logs `user_key` on two failure paths, and a third at debug. It is
  the caller's user id -- the one field that ties every other log line to a
  person, reproduced only on lines that exist to report a failure. `key_ref`
  keeps what those lines are for (are these failures one user or many?) and
  drops the rest, the same trade `question_ref` already makes for question text.

- `cache_manager.py` logs the `prefix` its caller asked to clear, and the
  interesting part is where that string came from: `POST /optimization/cache/clear`
  takes it as a query parameter and it reaches
  `scan_iter(match=f"{prefix}:*")`. So it was never only a log concern -- an
  unconstrained value there is a Redis glob, and `*` clears every namespace.
  Admin-only, and `clear()` with no parameter does the same thing on purpose, so
  this is not an escalation; it is a parameter that did not do what it said.

Both ends are checked, because they answer different questions: the HTTP
parameter so a bad value is a 422 rather than a surprise, and `CacheManager`
itself because that is where the glob is built and the class has callers other
than the endpoint.
"""

from __future__ import annotations

import asyncio
from typing import Any

import pytest

from app.services.caching.cache_manager import CACHE_PREFIX_PATTERN, CacheManager
from app.services.observability.log_safety import key_ref, question_ref


class TestAnIdentifierIsLoggedByReference:
    def test_the_same_key_gives_the_same_handle(self) -> None:
        """Correlating failures across lines is the only thing these logs need."""

        literal = "alice"
        rebuilt = "".join(["ali", "ce"])  # joined, not concatenated: literals get folded

        assert rebuilt is not literal, "the interpreter interned these; the test would prove less"
        assert key_ref(literal) == key_ref(rebuilt)

    def test_different_keys_give_different_handles(self) -> None:
        assert key_ref("alice") != key_ref("bob")

    def test_the_handle_does_not_contain_the_key(self) -> None:
        assert "alice" not in key_ref("alice")

    def test_it_does_not_collide_with_a_question_handle(self) -> None:
        """Two kinds of reference in the same log stream should not look alike."""

        assert key_ref("alice") != question_ref("alice")

    def test_none_is_handled(self) -> None:
        assert key_ref(None) == key_ref("")


class TestACachePrefixIsAName:
    @pytest.mark.parametrize("prefix", ["*", "?", "a*", "[abc]", "", "a" * 65, "with space", "a:b"])
    def test_a_pattern_is_refused(self, prefix: str) -> None:
        with pytest.raises(ValueError, match="cache prefix"):
            asyncio.run(CacheManager().clear_prefix(prefix))

    @pytest.mark.parametrize("prefix", ["retrieval", "route-decisions", "a", "A_1-b"])
    def test_a_name_is_accepted(self, prefix: str) -> None:
        asyncio.run(CacheManager().clear_prefix(prefix))  # must not raise

    def test_the_endpoint_and_the_cache_share_one_pattern(self) -> None:
        """Two copies of this rule would drift, and the loose one would win."""

        from typing import get_args

        from app.api.routes.optimization import performance

        query = get_args(performance.CachePrefix)[1]
        patterns = [getattr(item, "pattern", None) for item in query.metadata]

        assert CACHE_PREFIX_PATTERN in patterns, f"the endpoint validates against {patterns}"

    def test_clearing_a_namespace_leaves_the_others(self) -> None:
        cache = CacheManager()

        async def exercise() -> tuple[Any, Any]:
            await cache.l1_cache.set("keep:1", "kept", ttl=60)
            await cache.l1_cache.set("drop:1", "dropped", ttl=60)
            await cache.clear_prefix("drop")
            return await cache.l1_cache.get("keep:1"), await cache.l1_cache.get("drop:1")

        kept, dropped = asyncio.run(exercise())
        assert kept == "kept"
        assert dropped is None
