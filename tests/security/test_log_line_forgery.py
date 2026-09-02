"""A logged value must not be able to become a second log line.

`pythonsecurity:S5145` fires wherever caller-controlled data reaches a logging
call. Every site it found in this application logs an *identifier* -- an
execution id, a user key, a system name, a cache prefix -- so the risk is not
that a log discloses what someone asked (that is `question_ref`'s job, pinned in
test_no_question_text_in_logs.py) but that it discloses something that never
happened: a path parameter carrying `%0A` decodes to a newline, and one record
becomes two, the second one indistinguishable from a genuine entry.

Two defences, and they are not alternatives:

- the parameter is constrained at the edge (`ExecutionId`), so the character
  never enters -- which is what a scanner can see;
- the record factory escapes control characters wherever they came from, which
  covers the call sites nobody has audited and the ones not written yet.

These tests are for the second. They assert on `getMessage()` because that is
what every handler formats, and on the record rather than on captured output so
a handler's own formatting cannot mask a failure.
"""

from __future__ import annotations

import logging

import pytest

from app.services.observability.log_safety import install_control_character_escaping


@pytest.fixture(autouse=True)
def _escaping_installed():
    install_control_character_escaping()  # idempotent; the app installs it in lifespan


def _record(msg: str, *args: object) -> logging.LogRecord:
    return logging.getLogger("test.forgery").makeRecord("test.forgery", logging.INFO, __file__, 1, msg, args, None)


class TestAForgedLineCannotBeWritten:
    def test_a_newline_in_the_message_is_escaped(self) -> None:
        record = _record("started trace: abc\nINFO:root: user deleted everything")

        assert "\n" not in record.getMessage()
        assert "\\x0a" in record.getMessage()

    def test_a_newline_in_an_argument_is_escaped(self) -> None:
        """The f-string sites are covered by the message; %s sites by the args."""

        record = _record("started trace: %s", "abc\nINFO:root: forged")

        assert "\n" not in record.getMessage()

    def test_a_carriage_return_is_escaped(self) -> None:
        """Overwriting the current line is its own way of hiding an entry."""

        record = _record("user=%s", "alice\rroot")

        assert "\r" not in record.getMessage()

    def test_dict_style_arguments_are_covered(self) -> None:
        record = _record("user=%(who)s", {"who": "alice\nforged"})

        assert "\n" not in record.getMessage()


class TestTheEdgeRefusesTheCharacterOutright:
    """The other half, and the half a scanner can see.

    Discovered from the OpenAPI document rather than listed, because listing is
    how a guard ends up covering five of six routes: the sixth here -- the SSE
    endpoint -- had `max_length=128` and no character class, and was missed on
    the first pass precisely because nobody had written it down.
    """

    def test_no_execution_id_path_parameter_accepts_arbitrary_text(self) -> None:
        import app.api.main as main

        unconstrained = [
            f"{method.upper()} {path}"
            for path, operations in main.app.openapi()["paths"].items()
            for method, operation in operations.items()
            for parameter in operation.get("parameters", [])
            if parameter.get("name") == "execution_id"
            and parameter.get("in") == "path"
            and not parameter["schema"].get("pattern")
        ]

        assert not unconstrained, f"execution_id reaches the handler unvalidated on: {unconstrained}"


class TestOrdinaryLoggingIsUnchanged:
    def test_a_plain_message_survives_verbatim(self) -> None:
        record = _record("started trace: %s", "9f6c1b2e-0000-4000-8000-000000000000")

        assert record.getMessage() == "started trace: 9f6c1b2e-0000-4000-8000-000000000000"

    def test_a_tab_is_kept(self) -> None:
        """A tab cannot begin a record, and it is real formatting in table output."""

        assert "\t" in _record("a\tb").getMessage()

    def test_non_string_arguments_are_left_alone(self) -> None:
        record = _record("count=%d ratio=%.2f", 3, 0.5)

        assert record.getMessage() == "count=3 ratio=0.50"
