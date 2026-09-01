"""The router's chosen skill has to shape the answer.

`RouteDecision.skill` was set on every request, validated against
`VALID_SKILLS`, and read by nobody: `SynthesizerAgentService` hardcoded
`answer_with_citations`. Even wired, `skill_name` reached the model as a bare
header line -- the nine skills had no content behind them, so the choice could
not have changed an answer.

The shape is selected, never stacked: `templates.py` already puts a
question-inferred template in the prompt, and a second parallel block would have
put two competing answer shapes in front of the model.
"""

from __future__ import annotations

import asyncio

import pytest

from app.agents.shared.config import SKILL_DEFAULT, VALID_SKILLS
from app.agents.synthesizer.skills import (
    GENERAL_SKILLS,
    SKILL_QUERY_TYPES,
    SKILL_TEMPLATES,
    skill_answer_template,
)
from app.agents.synthesizer.templates import get_answer_template, infer_query_type

ATTACK_QUESTION = "这次入侵是怎么发生的"


class TestEverySkillIsAccountedFor:
    def test_no_skill_is_left_without_guidance(self) -> None:
        """A skill the router can pick but nothing describes is the bug this
        module exists to close, so the sets are checked rather than trusted."""
        covered = SKILL_TEMPLATES.keys() | SKILL_QUERY_TYPES.keys() | GENERAL_SKILLS

        assert VALID_SKILLS <= covered

    def test_no_guidance_is_written_for_a_skill_the_router_cannot_pick(self) -> None:
        assert (SKILL_TEMPLATES.keys() | SKILL_QUERY_TYPES.keys()) <= VALID_SKILLS

    def test_a_skill_is_described_once(self) -> None:
        """Own shape, mapped shape, or question-inferred -- exactly one."""
        for skill in VALID_SKILLS:
            homes = sum(
                (
                    skill in SKILL_TEMPLATES,
                    skill in SKILL_QUERY_TYPES,
                    skill in GENERAL_SKILLS,
                )
            )
            assert homes == 1, f"{skill} is described {homes} times"

    @pytest.mark.parametrize("skill", sorted(SKILL_TEMPLATES))
    def test_each_authored_template_teaches_the_internal_marker(self, skill: str) -> None:
        """`output_filter` renumbers to `[1]` after DLP settles which citations
        survive; a template teaching reader-facing numbers would teach the model
        to invent numbering the pipeline is about to overwrite."""
        template = SKILL_TEMPLATES[skill]

        assert "[E1]" in template
        assert "[1]" not in template.replace("[E1]", "").replace("[E2]", "").replace("[E3]", "")

    @pytest.mark.parametrize("skill", sorted(SKILL_TEMPLATES))
    def test_each_authored_template_requires_citations(self, skill: str) -> None:
        assert "MUST" in SKILL_TEMPLATES[skill]


class TestSelection:
    def test_a_skill_with_its_own_shape_uses_it(self) -> None:
        assert skill_answer_template("timeline_builder", SKILL_DEFAULT) is SKILL_TEMPLATES["timeline_builder"]

    def test_a_mapped_skill_reaches_the_existing_template(self) -> None:
        """`compare_entities` names a shape `templates.py` already describes.
        Mapping means an LLM-detected comparison gets it even when the wording
        carries none of the keywords `infer_query_type` looks for."""
        keyword_free = "A 与 B 各自适合什么场景"

        assert infer_query_type(keyword_free) != "comparison"
        assert skill_answer_template("compare_entities", keyword_free) == get_answer_template("comparison")

    def test_a_general_skill_still_infers_from_the_question(self) -> None:
        for question in ("什么是 RAG", "对比 A 和 B 的区别"):
            assert skill_answer_template(SKILL_DEFAULT, question) == get_answer_template(infer_query_type(question))

    def test_an_unknown_skill_degrades_to_the_previous_behaviour(self) -> None:
        """Not to no guidance: an unrecognised value must land where the code
        stood before this module existed."""
        assert skill_answer_template("not_a_skill", "什么是 RAG") == get_answer_template(infer_query_type("什么是 RAG"))

    @pytest.mark.parametrize("blank", ["", "   ", None])
    def test_a_missing_skill_is_the_default_skill(self, blank) -> None:
        assert skill_answer_template(blank, "什么是 RAG") == skill_answer_template(SKILL_DEFAULT, "什么是 RAG")


class TestItReachesThePrompt:
    """The wiring, not the table: service -> generation -> prompt."""

    @staticmethod
    def _prompt_for(skill: str, question: str = ATTACK_QUESTION) -> str:
        from app.agents.synthesizer.service import SynthesizerAgentService
        from app.domain.contracts import EvidenceItem
        from app.domain.workflow import ContextBundle
        from app.orchestration.request import OrchestrationRequest

        seen: dict[str, str] = {}

        def _generate(question_text: str, skill_name: str, **kwargs) -> dict:
            import app.agents.synthesizer.generation as generation

            seen["prompt"] = generation._build_prompt_with_language(
                question_text,
                "zh",
                skill_name,
                vector_context=str(kwargs.get("vector_context") or ""),
            )
            return {"answer": "占位 [E1]", "citations": []}

        item = EvidenceItem(
            content="evidence",
            source="a.pdf",
            document_id="a.pdf",
            version=1,
            retriever="vector",
        )
        service = SynthesizerAgentService(generate=_generate)
        asyncio.run(
            service.synthesize_candidate(
                OrchestrationRequest(question=question),
                ContextBundle(evidence=(item,), rendered_context="[E1] evidence"),
                (),
                skill,
            )
        )
        return seen["prompt"]

    def test_the_chosen_skill_changes_the_template(self) -> None:
        assert "timeline" in self._prompt_for("timeline_builder").lower()
        assert "attack" in self._prompt_for("cyber_attack_analysis").lower()

    def test_two_skills_on_one_question_produce_different_prompts(self) -> None:
        """The point of the whole item: before this, the skill could not change
        anything, so the same question always produced the same prompt."""
        assert self._prompt_for("timeline_builder") != self._prompt_for("incident_response_playbook")

    def test_the_default_skill_keeps_todays_prompt(self) -> None:
        prompt = self._prompt_for(SKILL_DEFAULT, "什么是 RAG")

        assert get_answer_template("concept").strip() in prompt

    def test_only_one_template_block_reaches_the_model(self) -> None:
        """Skill and query type answer the same question; two blocks would put
        two competing answer shapes in one prompt."""
        assert self._prompt_for("timeline_builder").count("答案模板指导") == 1


def test_the_graph_node_passes_the_routers_choice() -> None:
    """The node reads `state["route"].skill`; a default here would make every
    other test in this file describe a table nothing consults."""
    import inspect

    from app.orchestration.langgraph.nodes import WorkflowNodeRuntime

    source = inspect.getsource(WorkflowNodeRuntime.synthesizer)

    assert "candidate_synthesizer(request, context, tool_results, skill)" in source
    assert 'getattr(routed, "skill", "")' in source
