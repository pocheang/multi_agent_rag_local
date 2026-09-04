"""The NLI stage: off the event loop, honest about which scorer ran, and able
to score Chinese.

It had never executed. `CASCADE_ENABLE_LEVEL2` gated it -- `CascadeLevel.NLI_BATCH`
being level 2 -- and defaulted False, while CLAUDE.md listed NLI among the checks
answer validation performs. Three separate defects meant turning it on would have
been worse than leaving it off, and each has a test below.
"""

from __future__ import annotations

import sys
import threading
from typing import Any

import pytest

from app.agents.validation import nli as nli_module
from app.agents.validation.cascade import ValidationCascade
from app.agents.validation.models import CascadeLevel, ValidationRequest
from app.agents.validation.nli import NLIValidator, is_predominantly_latin, tokenize

_ZH_SOURCE = "根据财报，本季度营业成本为一千二百万元，同比上升百分之三。运营团队共有四十五人。"
_EN_SOURCE = "According to the report the operating cost was twelve million this quarter, up three percent."


def _request(answer: str, source: str) -> ValidationRequest:
    return ValidationRequest.from_compatibility(
        query="what were the costs",
        answer=answer,
        source_docs=[{"content": source}],
        citations=(),
    )


@pytest.fixture
def no_model(monkeypatch):
    """Force the deterministic path regardless of what is installed locally."""

    monkeypatch.setattr(nli_module, "load_nli_cross_encoder", lambda: None)


# --- 1. it must not block the event loop ------------------------------------


class _RecordingModel:
    """Records the thread its forward pass ran on."""

    def __init__(self, score: float = 0.9, delay: float = 0.0) -> None:
        self.score = score
        self.delay = delay
        self.thread: str | None = None

    def predict(self, pairs: list[tuple[str, str]]) -> Any:
        import time

        import numpy as np

        self.thread = threading.current_thread().name
        if self.delay:
            time.sleep(self.delay)
        return np.array([[0.0, 0.0, self.score]] * len(pairs))


@pytest.mark.asyncio
async def test_predict_never_runs_on_the_event_loop(monkeypatch):
    """The assertion that would have caught it.

    `model.predict` is a synchronous cross-encoder forward pass and was awaited
    directly inside `async def`, so it held the loop for its whole duration --
    the defect class this repository has already fixed three times.
    """

    model = _RecordingModel()
    monkeypatch.setattr(nli_module, "load_nli_cross_encoder", lambda: model)

    await NLIValidator().validate(_request("The operating cost was twelve million this quarter.", _EN_SOURCE))

    assert model.thread is not None
    assert model.thread != threading.current_thread().name


@pytest.mark.asyncio
async def test_a_slow_model_falls_back_rather_than_hanging(monkeypatch):
    """Asserts the reported reason, not a wall-clock bound: a clock is a bad
    thing to assert on in CI."""

    monkeypatch.setattr(nli_module, "load_nli_cross_encoder", lambda: _RecordingModel(delay=0.5))
    validator = NLIValidator()
    validator.timeout_ms = 50

    result = await validator.validate(_request("The operating cost was twelve million this quarter.", _EN_SOURCE))

    assert result.backend == "lexical"
    assert result.fallback_reason == "timeout"


def test_a_missing_model_never_reaches_the_network(monkeypatch):
    """`local_files_only=True` turns "not downloaded" into an instant None
    instead of an untimed fetch inside a request."""

    seen: dict[str, Any] = {}

    class _FakeCrossEncoder:
        def __init__(self, name: str, **kwargs: Any) -> None:
            seen["name"] = name
            seen.update(kwargs)

    module = type(sys)("sentence_transformers")
    module.CrossEncoder = _FakeCrossEncoder
    monkeypatch.setitem(sys.modules, "sentence_transformers", module)
    nli_module.load_nli_cross_encoder.cache_clear()
    try:
        nli_module.load_nli_cross_encoder()
    finally:
        nli_module.load_nli_cross_encoder.cache_clear()

    assert seen.get("local_files_only") is True


# --- 2. the deterministic path must score Chinese ---------------------------


def test_the_tokenizer_splits_chinese_into_characters():
    """`re.findall(r"\\w+", ...)` made a whole Chinese clause one token, so only
    a verbatim copy could ever match."""

    assert len(tokenize("本季度营业成本")) > 1
    assert tokenize("operating cost") == {"operating", "cost"}


@pytest.mark.asyncio
async def test_a_chinese_paraphrase_of_its_evidence_is_supported(no_model: None):
    """The assertion that would have caught the tokenizer bug.

    A verbatim clause copy cannot discriminate -- it scored 1.00 under both the
    old and the new tokenizer. A paraphrase is the case that separates them:
    0.00 before, ~0.86 after. Synthesis paraphrases by construction, so this was
    the common shape, and a 0.00 becomes `factuality < 0.7` and then a rejected
    answer.
    """

    result = await NLIValidator().validate(_request("营业成本本季度达到一千二百万元。", _ZH_SOURCE))

    assert result.confidence_score > 0.7
    assert result.issues == []


@pytest.mark.asyncio
async def test_a_chinese_answer_recombining_two_sources_is_supported(no_model: None):
    result = await NLIValidator().validate(_request("营业成本为一千二百万元，运营团队四十五人。", _ZH_SOURCE))

    assert result.confidence_score > 0.7


@pytest.mark.asyncio
async def test_a_chinese_answer_unrelated_to_its_evidence_is_flagged(no_model: None):
    """The negative direction, so this suite cannot pass by the stage doing
    nothing."""

    result = await NLIValidator().validate(_request("公司在南极洲开设了新的分支机构并雇佣了企鹅担任顾问。", _ZH_SOURCE))

    assert result.confidence_score < 0.5
    assert result.issues


# --- 3. the model is English, and that must be reported ---------------------


def test_latin_and_cjk_text_are_told_apart():
    assert is_predominantly_latin("the operating cost was twelve million")
    assert not is_predominantly_latin("本季度营业成本为一千二百万元")


@pytest.mark.asyncio
async def test_chinese_text_does_not_reach_the_english_cross_encoder(monkeypatch):
    """`NLI_MODEL_NAME` is an English model and the code reads `scores[:, 2]` as
    its entailment column, which is model-specific. On Chinese its output is
    noise, so the deterministic path runs and says so."""

    model = _RecordingModel()
    monkeypatch.setattr(nli_module, "load_nli_cross_encoder", lambda: model)

    result = await NLIValidator().validate(_request("营业成本本季度达到一千二百万元。", _ZH_SOURCE))

    assert model.thread is None, "the English cross-encoder must not be called on Chinese"
    assert result.backend == "lexical"
    assert result.fallback_reason == "non_latin_text"


@pytest.mark.asyncio
async def test_the_batch_handed_to_the_model_is_bounded(monkeypatch):
    """An unbounded batch is what makes a timeout on this stage unpredictable."""

    captured: list[int] = []

    class _CountingModel(_RecordingModel):
        def predict(self, pairs: list[tuple[str, str]]) -> Any:
            captured.append(len(pairs))
            return super().predict(pairs)

    monkeypatch.setattr(nli_module, "load_nli_cross_encoder", lambda: _CountingModel())
    validator = NLIValidator(max_sentences=2)

    answer = " ".join(f"The operating cost was twelve million in quarter {i}." for i in range(10))
    await validator.validate(_request(answer, _EN_SOURCE))

    assert captured == [2]


# --- the cascade wiring -----------------------------------------------------


def _cascade(**overrides: Any) -> ValidationCascade:
    config = {
        "enable_rules": True,
        "enable_citations": True,
        "enable_nli": True,
        "enable_deep": False,
        **overrides,
    }
    return ValidationCascade(config=config)


@pytest.mark.parametrize(
    ("switch", "level"),
    [
        ("enable_rules", CascadeLevel.RULE_BASED),
        ("enable_citations", CascadeLevel.CITATION_CHECK),
        ("enable_nli", CascadeLevel.NLI_BATCH),
    ],
)
@pytest.mark.asyncio
async def test_every_cascade_switch_gates_the_stage_it_names(switch: str, level: CascadeLevel, no_model: None):
    """The assertion that would have caught level2/level3 naming the wrong stages.

    `enable_level2` gated the NLI check and `enable_level3` the citation check,
    so reading the configuration told you the opposite of what ran.
    """

    on = await _cascade().validate("q", "The operating cost was twelve million.", [{"content": _EN_SOURCE}], [])
    off = await _cascade(**{switch: False}).validate(
        "q", "The operating cost was twelve million.", [{"content": _EN_SOURCE}], []
    )

    assert level in {result.level for result in on.level_results}
    assert level not in {result.level for result in off.level_results}


def test_the_declared_stage_order_matches_the_order_they_run_in():
    """`_weighted_confidence` applies its weights positionally."""

    assert list(CascadeLevel) == [
        CascadeLevel.RULE_BASED,
        CascadeLevel.CITATION_CHECK,
        CascadeLevel.NLI_BATCH,
        CascadeLevel.DEEP_LLM,
    ]


def test_no_cascade_timeout_is_stored_without_a_consumer():
    """`test_settings_have_readers` passed for two dead timeouts, because
    assigning a field to an attribute nobody reads counts as a reader."""

    cascade = _cascade()
    timeouts = {name for name in vars(cascade) if name.endswith("_timeout_ms")}

    assert timeouts == {"nli_timeout_ms", "deep_timeout_ms"}
    assert cascade.deep_validator.timeout_ms == cascade.deep_timeout_ms


@pytest.mark.asyncio
async def test_validation_method_names_the_backend_that_ran(no_model: None):
    """ "standard" must mean the cross-encoder ran, not that the stage was
    reached -- the model being absent is ordinary."""

    from app.agents.validation.public import validate_answer

    # Long enough to clear `quick_validation`'s minimum-length rejection, which
    # `validate_answer` enforces and which short-circuits every stage.
    answer = (
        "According to the quarterly report the operating cost was twelve million "
        "this quarter, which represents an increase of three percent over the "
        "previous reporting period."
    )

    result = await validate_answer("q", answer, [{"content": _EN_SOURCE}], [])

    assert result.validation_method == "standard_lexical"
