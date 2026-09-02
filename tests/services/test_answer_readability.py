"""The answer a reader sees must not contain the machinery that produced it.

Found by reading one on screen. A single question came back as:

    基于当前可用证据，基于当前本地检索结果，我对"What is reciprocal rank fusion?基于当前
    可用证据，"的回答如下： 1.基于当前可用证据， [1] document=https://<PATH_1>
    source=https://<PATH_2> layer=web; retriever=web Reciprocal Rank Fusion ...
    2.基于当前可用证据，无 答案模板指导（Skill: answer_with_citations）： Answer
    template for concept explanation: ... Citation rules: - EVERY factual claim
    MUST have an evidence-marker citation ...

Four separate defects, in two files:

`LocalEvidenceChatModel` (app/services/models/runtime.py)
  1. narrated itself ("我对…的回答如下") and closed with a paragraph about
     configuring Ollama;
  2. echoed `ContextBuilder`'s addressing header (`[E1] document=…; layer=…;
     retriever=…`), which is metadata, not prose;
  3. `_extract_section` terminated only on labels ending in `上下文:`, so the last
     section ran to the end of the prompt and swallowed the answer template --
     the model's own instructions came back as part of the answer.

`apply_sentence_grounding` (app/services/retrieval/citation_grounding.py)
  4. treated a bare citation marker as a sentence, scored it unsupported, and
     prefixed it -- hedging the attribution rather than the claim.
"""

from __future__ import annotations

import re

import pytest

from app.services.models.runtime import LocalEvidenceChatModel
from app.services.retrieval.citation_grounding import apply_sentence_grounding

PROMPT = """[Language: en]
技能: answer_with_citations

用户问题:
What is reciprocal rank fusion?

记忆上下文:
无

向量检索上下文:
无

图谱上下文:
无

联网补充上下文:
[E1] document=https://example.org/rrf; source=https://example.org/rrf; layer=web; retriever=web
Reciprocal Rank Fusion merges rankings mathematically. It gives credit to items ranked high in several lists.

答案模板指导（Skill: answer_with_citations）：
Answer template for concept explanation:
1. Core definition with citation [E1]
Citation rules:
- EVERY factual claim MUST have an evidence-marker citation, e.g. [E1]
"""


@pytest.fixture
def answer() -> str:
    return LocalEvidenceChatModel().invoke([("human", PROMPT)]).content


class TestTheOfflineAnswerIsAnAnswer:
    def test_the_prompt_does_not_come_back_in_it(self, answer: str) -> None:
        """The defect that made the answer unreadable: the template section was
        parsed as part of the last evidence block."""
        assert "答案模板指导" not in answer
        assert "Answer template" not in answer
        assert "EVERY factual claim MUST" not in answer

    def test_the_addressing_header_is_not_prose(self, answer: str) -> None:
        for fragment in ("document=", "source=", "layer=web", "retriever="):
            assert fragment not in answer

    def test_it_does_not_narrate_itself(self, answer: str) -> None:
        """A note about which backend ran belongs in the trace, not in every
        answer the reader has to read past."""
        assert "回答如下" not in answer
        assert "Ollama" not in answer
        assert "离线后端" not in answer

    def test_the_placeholder_for_an_empty_section_is_not_content(self, answer: str) -> None:
        assert not answer.lstrip().startswith("无")

    def test_it_carries_the_marker_of_what_it_quoted(self, answer: str) -> None:
        """Without a marker there is nothing for `output_filter` to renumber, so
        the reference list it appends points at citations the text never made."""
        assert "[E1]" in answer

    def test_it_says_something(self, answer: str) -> None:
        assert "Reciprocal Rank Fusion" in answer

    def test_no_evidence_is_reported_as_no_evidence(self) -> None:
        empty = PROMPT.replace(
            "[E1] document=https://example.org/rrf; source=https://example.org/rrf; layer=web; retriever=web\n"
            "Reciprocal Rank Fusion merges rankings mathematically. "
            "It gives credit to items ranked high in several lists.",
            "无",
        )
        text = LocalEvidenceChatModel().invoke([("human", empty)]).content

        assert "[E" not in text
        assert "检索" in text


class TestGroundingLeavesStructureAlone:
    EVIDENCE = ["Reciprocal Rank Fusion merges rankings mathematically."]

    def test_a_bare_citation_marker_is_not_hedged(self) -> None:
        """`基于当前可用证据，[E1]` reads as doubt about the citation itself."""
        text = "Reciprocal Rank Fusion merges rankings mathematically.\n\n[E1]"
        grounded, _ = apply_sentence_grounding(text, self.EVIDENCE)

        assert grounded == text

    def test_a_url_is_not_split_through_the_middle(self) -> None:
        """The dot in a hostname is not a full stop, and hedging what followed it
        spliced the prefix into the link: `https://x.基于当前可用证据，example/a`."""
        text = "See https://arxiv.org/abs/2505.08728 for the assessment framework. [E1]"
        grounded, _ = apply_sentence_grounding(text, self.EVIDENCE)

        assert "https://arxiv.org/abs/2505.08728" in grounded

    def test_a_heading_is_not_hedged(self) -> None:
        text = "Merges rankings mathematically. [E1]\n\n**参考来源**\n\n- [1] https://example.org/rrf"
        grounded, _ = apply_sentence_grounding(text, self.EVIDENCE)

        assert "**参考来源**" in grounded
        assert "- [1] https://example.org/rrf" in grounded

    def test_untouched_text_keeps_its_whitespace(self) -> None:
        """Rejoining the pieces with one separator reflowed paragraph breaks and
        list indentation into a single space."""
        text = "Merges rankings mathematically. [E1]\n\n- and gives credit to top-ranked items. [E1]"
        grounded, _ = apply_sentence_grounding(text, self.EVIDENCE)

        assert "\n\n- " in grounded

    def test_the_hedge_goes_before_the_claim_not_the_bullet(self) -> None:
        text = "- entirely unrelated assertion about Argentine monetary policy."
        grounded, _ = apply_sentence_grounding(text, self.EVIDENCE)

        assert grounded.startswith("- 基于当前可用证据，")

    def test_a_genuinely_unsupported_claim_is_still_hedged(self) -> None:
        """The fixes must not turn the check off -- that would trade a cosmetic
        bug for a truthfulness one."""
        text = "Quantum tunnelling drives inflation in Argentina."
        grounded, report = apply_sentence_grounding(text, self.EVIDENCE)

        assert grounded.startswith("基于当前可用证据，")
        assert report["rewritten_sentences"] == 1

    def test_a_supported_claim_is_left_alone(self) -> None:
        text = "Reciprocal Rank Fusion merges rankings mathematically. [E1]"
        grounded, report = apply_sentence_grounding(text, self.EVIDENCE)

        assert grounded == text
        assert report["rewritten_sentences"] == 0


class TestEveryRetrievedSourceIsUsed:
    """One paragraph and one reference for a four-source answer.

    `_extract_section` has now been wrong in both directions. Terminating only
    on labels ending in `上下文:` let the last section run to the end of the
    prompt and swallow the answer template. Replacing that with "a short line
    ending in a colon" cut the section at *every piece of evidence*, because
    `[E2] document=https:` reaches a colon within a few characters -- so all but
    the first excerpt was silently discarded, and the reader saw a single
    citation for a search that had returned four.

    The terminator is now the set of labels `_build_prompt_with_language`
    actually writes.
    """

    @staticmethod
    def _rendered(count: int) -> str:
        return "\n\n".join(
            f"[E{i}] document=https://example.org/{i}, version=1; "
            f"source=https://example.org/{i}; layer=web; retriever=web\n"
            f"Fact number {i} about reciprocal rank fusion, stated plainly."
            for i in range(1, count + 1)
        )

    def _answer_for(self, count: int) -> str:
        import app.agents.synthesizer.generation as generation

        prompt = generation._build_prompt_with_language(
            "What is reciprocal rank fusion?",
            "en",
            "answer_with_citations",
            vector_context=self._rendered(count),
        )
        return LocalEvidenceChatModel().invoke([("human", prompt)]).content

    def test_four_sources_produce_four_citations(self) -> None:
        answer = self._answer_for(4)

        assert sorted(set(re.findall(r"\[E\d+\]", answer))) == ["[E1]", "[E2]", "[E3]", "[E4]"]

    def test_a_url_in_the_evidence_does_not_end_the_section(self) -> None:
        """The exact character that broke it: the colon in `https:`."""
        assert "[E2]" in self._answer_for(2)

    def test_each_marker_keeps_its_own_excerpt(self) -> None:
        """Misattribution would be worse than truncation: it credits a claim to a
        source that does not support it."""
        answer = self._answer_for(4)
        pairs = re.findall(r"Fact number (\d+)[^\n]*\[E(\d+)\]", answer)

        assert pairs, "no cited excerpts in the answer"
        for fact, marker in pairs:
            assert fact == marker, f"[E{marker}] carries fact {fact}"
