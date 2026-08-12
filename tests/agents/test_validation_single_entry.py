"""Regression coverage for validation ownership and its one production entry."""

import ast
import inspect
from importlib import import_module

import pytest

from app.agents.validation.rules import CascadeLevel, ValidationCascadeResult


def _cascade_result(*, confidence: float = 0.42) -> ValidationCascadeResult:
    return ValidationCascadeResult(
        has_issues=False,
        confidence_score=confidence,
        highest_level_reached=CascadeLevel.RULE_BASED,
        all_issues=[],
        total_execution_time_ms=1,
        execution_time_ms=1,
        level_results=[],
    )


@pytest.mark.parametrize(
    ("module_name", "class_name"),
    [
        ("app.agents.validation.rules", "RuleValidator"),
        ("app.agents.validation.citations", "CitationValidator"),
        ("app.agents.validation.nli", "NLIValidator"),
        ("app.agents.validation.deep", "DeepValidator"),
        ("app.agents.validation.cascade", "ValidationCascade"),
    ],
)
def test_each_validation_stage_has_a_concrete_owner(module_name: str, class_name: str) -> None:
    """Moving only import aliases would leave the oversized implementation intact."""
    module = import_module(module_name)
    validator = getattr(module, class_name, None)

    assert validator is not None
    assert validator.__module__ == module_name


def test_answer_validator_imports_cascade_from_concrete_production_owner() -> None:
    """Production must not depend on the legacy compatibility facade."""
    from app.agents import answer_validator_agent

    module_ast = ast.parse(inspect.getsource(answer_validator_agent))
    cascade_import_owners = {
        node.module
        for node in module_ast.body
        if isinstance(node, ast.ImportFrom)
        and any(alias.name == "ValidationCascade" for alias in node.names)
    }

    assert cascade_import_owners == {"app.agents.validation.cascade"}


@pytest.mark.asyncio
async def test_disabled_legacy_switch_cannot_bypass_validation_entry(monkeypatch) -> None:
    """A compatibility switch must not revive the superseded validator engine."""
    from app.agents import answer_validator_agent
    from app.agents.validation.cascade import ValidationCascade

    calls = 0

    async def validate_once(self, query, answer, source_docs, citations):
        nonlocal calls
        calls += 1
        return _cascade_result()

    monkeypatch.setattr(answer_validator_agent, "CASCADE_USE_FOR_VALIDATION", False)
    monkeypatch.setattr(answer_validator_agent, "_validation_cascade", None)
    monkeypatch.setattr(answer_validator_agent, "_cascade_load_attempted", False)
    monkeypatch.setattr(ValidationCascade, "validate", validate_once)

    result = await answer_validator_agent.validate_answer(
        "What is Python?",
        "Python is a readable programming language used for web services and data analysis.",
        [{"id": "doc-1", "content": "Python is a programming language."}],
        [{"doc_id": "doc-1"}],
    )

    assert calls == 1
    assert result.validation_details.factual_consistency == 0.42


@pytest.mark.asyncio
async def test_validation_entry_failure_does_not_execute_legacy_engine(monkeypatch) -> None:
    """Catching the entry failure and running duplicate logic creates two production paths."""
    from app.agents import answer_validator_agent

    class EntryFailed(RuntimeError):
        pass

    class FailingCascade:
        async def validate(self, query, answer, source_docs, citations):
            raise EntryFailed("single validation entry failed")

    monkeypatch.setattr(answer_validator_agent, "_get_validation_cascade", lambda: FailingCascade())

    with pytest.raises(EntryFailed, match="single validation entry failed"):
        await answer_validator_agent.validate_answer(
            "What is Python?",
            "Python is a readable programming language used for web services and data analysis.",
            [{"id": "doc-1", "content": "Python is a programming language."}],
            [{"doc_id": "doc-1"}],
        )


@pytest.mark.asyncio
async def test_run_cascade_compatibility_alias_enters_validate() -> None:
    """The old method name may remain only as a forwarding compatibility alias."""
    from app.agents.validation_cascade import ValidationCascade

    sentinel = _cascade_result(confidence=0.73)

    class ProbeCascade(ValidationCascade):
        async def validate(self, query, answer, source_docs, citations):
            return sentinel

    result = await ProbeCascade().run_cascade("query", "answer", [], [])

    assert result is sentinel
