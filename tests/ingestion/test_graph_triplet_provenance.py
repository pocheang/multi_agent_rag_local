"""A triplet's confidence must say how it was produced.

`extract_graph_triplets` stamped `confidence=0.7, method="legacy"` on every
triplet regardless of extractor, so `filter_triplets(min_confidence=...)` could
not tell an LLM-extracted relation from a regex-chained one and its threshold was
inert.

That mattered because the rule extractor does not find relations. It takes the
ten most *frequent* `ENTITY_PATTERN` matches -- and that pattern matches any 2-12
character CJK run, so in Chinese it matches nearly every word -- then pairs them
by adjacent frequency rank, which is an artefact of sort order, and labels every
pair in a chunk with one relation keyed off the whole chunk's wording.

And it was the default path, not an edge case: `MODEL_BACKEND=local` is what a
fresh checkout runs, the offline stand-in cannot emit the required JSON array, so
`extract_triplets` fell through to rules on every chunk. The graph filled with
invented edges that the graph route then served as evidence.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app.ingestion import graph_extractor
from app.ingestion.graph_extractor import (
    LLM_TRIPLET_CONFIDENCE,
    RULE_TRIPLET_CONFIDENCE,
    extract_graph_triplets_with_diagnostics,
    extract_triplets,
    infer_relation,
)
from app.services.parser_profiles import choose_parser_profile
from app.tools.graph.core import _relation_weight

# Enough distinct repeated entities for the rule extractor to chain some pairs.
_TEXT = "Alpha depends on Beta. Alpha and Gamma and Beta and Delta. Alpha Beta Gamma Delta Epsilon."


@pytest.fixture
def rules_mode(monkeypatch):
    """Force the configured rule extractor, without an LLM in the loop."""

    settings = graph_extractor.get_settings()
    monkeypatch.setattr(
        graph_extractor,
        "get_settings",
        lambda: settings.model_copy(update={"graph_extraction_mode": "rules"}),
    )


@pytest.fixture
def llm_fails(monkeypatch):
    """An LLM that raises, so extraction falls back to rules."""

    settings = graph_extractor.get_settings()
    monkeypatch.setattr(
        graph_extractor,
        "get_settings",
        lambda: settings.model_copy(update={"graph_extraction_mode": "auto"}),
    )

    def explode(text: str):
        raise RuntimeError("no model configured")

    monkeypatch.setattr(graph_extractor, "extract_triplets_llm", explode)


def test_rule_triplets_carry_the_rule_method_and_confidence(rules_mode: None) -> None:
    triplets = extract_triplets(_TEXT)

    assert triplets, "the fixture text must yield rule triplets for this suite to mean anything"
    assert {item.method for item in triplets} == {"rules"}
    assert {item.confidence for item in triplets} == {RULE_TRIPLET_CONFIDENCE}


def test_the_default_min_confidence_excludes_rule_triplets(rules_mode: None) -> None:
    """The assertion that would have caught it.

    Before this, every triplet was stamped 0.7 and sailed through.
    """

    kept, diagnostics = extract_graph_triplets_with_diagnostics(_TEXT, min_confidence=0.5)

    assert kept == []
    assert diagnostics["discarded_low_confidence"] > 0
    assert diagnostics["rules"] == diagnostics["discarded_low_confidence"]


def test_an_llm_failure_is_recorded_as_a_fallback_not_as_an_llm_result(llm_fails: None) -> None:
    """ "Configured for rules" and "the LLM is broken" are different facts and
    were previously indistinguishable."""

    triplets = extract_triplets(_TEXT)

    assert {item.method for item in triplets} == {"rules_llm_fallback"}
    assert {item.confidence for item in triplets} == {RULE_TRIPLET_CONFIDENCE}


def test_llm_triplets_survive_the_default_threshold(monkeypatch) -> None:
    settings = graph_extractor.get_settings()
    monkeypatch.setattr(
        graph_extractor,
        "get_settings",
        lambda: settings.model_copy(update={"graph_extraction_mode": "auto"}),
    )
    monkeypatch.setattr(
        graph_extractor,
        "extract_triplets_llm",
        lambda text: [("Alpha", "DEPENDS_ON", "Beta")],
    )

    kept, diagnostics = extract_graph_triplets_with_diagnostics(_TEXT, min_confidence=0.5)

    assert [(item.head, item.relation, item.tail) for item in kept] == [("Alpha", "DEPENDS_ON", "Beta")]
    assert kept[0].method == "llm"
    assert kept[0].confidence == LLM_TRIPLET_CONFIDENCE
    assert diagnostics["discarded_low_confidence"] == 0


_PROFILE_SAMPLES = ("report.pdf", "scan.png", "security_policy.md", "notes.txt")


@pytest.mark.parametrize("filename", _PROFILE_SAMPLES)
def test_every_shipped_parser_profile_threshold_excludes_rule_confidence(filename: str) -> None:
    """Pins a coupling between two files that is otherwise invisible.

    `RULE_TRIPLET_CONFIDENCE` only does its job while it sits below every
    `graph_min_confidence` in app/services/parser_profiles.py. Lowering one of
    those without reading this constant would silently re-admit rule triplets.
    """

    profile = choose_parser_profile(Path(filename))

    assert float(profile["graph_min_confidence"]) > RULE_TRIPLET_CONFIDENCE


def test_the_samples_above_reach_every_profile_the_module_can_return() -> None:
    """Discovered, not listed: a fifth profile added without a sample here would
    otherwise be excluded from the check above and nobody would notice."""

    source = Path("app/services/parser_profiles.py").read_text(encoding="utf-8")
    declared = set(re.findall(r'"name":\s*"([a-z_]+)"', source))
    reached = {choose_parser_profile(Path(name))["name"] for name in _PROFILE_SAMPLES}

    assert declared == reached


def test_the_rule_extractors_default_relation_is_treated_as_noise() -> None:
    """Both halves asserted together, so renaming either one fails the test.

    `_NOISY_RELATIONS` contained "related" but not "related_to", which is what
    `infer_relation` actually emits when no keyword matches -- so the junkiest
    edges scored 0.6 and survived the filter that exists to drop them. This is
    the only mitigation available for graphs already written: Neo4j persists no
    extraction method, and every existing edge carries the same 0.7.
    """

    assert infer_relation("no keywords here at all", "Alpha", "Beta") == "RELATED_TO"
    assert _relation_weight("RELATED_TO") == 0.0
