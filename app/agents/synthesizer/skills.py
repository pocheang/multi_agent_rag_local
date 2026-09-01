"""What each router-chosen skill asks the answer to look like.

The router's prompt has always offered nine skills and `RouteDecision.skill` has
always carried the choice, but nothing read it: `SynthesizerAgentService`
hardcoded `answer_with_citations`, and even if it had not, `skill_name` reached
the model as a bare header line with no content behind it. The model saw one
word and had nothing to do with it.

**One template block, not two.** `templates.py` already infers a *query type*
from the question by keyword and puts its template in the prompt, so authoring a
second, parallel set of skill templates would have put two competing answer
shapes in front of the model. Skill and query type are two answers to the same
question -- what shape should this answer take -- and the skill is the better
one: the router chose it with an LLM that read the whole question, while
`infer_query_type` matches a keyword list. So the skill decides, and it decides
by *selecting* a template rather than by adding one:

- a skill with its own shape below uses it;
- `compare_entities` maps onto the existing `COMPARISON_TEMPLATE`, which is the
  same shape already written -- and mapping it means an LLM-detected comparison
  now gets that template even when the wording carries none of the keywords
  `infer_query_type` looks for. The same reasoning as "the route is an
  instruction, not a hint" on the retrieval side;
- the general-purpose skills fall through to today's behaviour, keyword
  inference included, because for them the question really is the best signal.

Everything here teaches the **internal** `[E{k}]` marker, never `[1]`.
`output_filter` renumbers by first appearance after DLP settles which citations
survive; a prompt that taught reader-facing numbers would be teaching the model
to invent numbering the pipeline is about to overwrite.
"""

from __future__ import annotations

from app.agents.shared.config import SKILL_DEFAULT
from app.agents.synthesizer.templates import QueryType, get_answer_template, infer_query_type

TIMELINE_TEMPLATE = """
Answer template for building a timeline of events:

1. One line stating the span the evidence actually covers, with a citation
2. Events in chronological order, each on its own line and each cited:
   <date or period>: <what happened> [E1]
3. Gaps and ordering you could not establish, stated explicitly

Citation rules:
- EVERY event MUST carry the citation for the source that dates it
- Never infer a date from position in a document; if a source gives an event but
  no date, list it as undated rather than guessing where it belongs
- If two sources disagree on a date, give both with their citations rather than
  choosing: "<source A> 记为 <date1> [E1]，<source B> 记为 <date2> [E2]"
- Relative wording ("三个月后") stays relative unless a source anchors it

Example structure:
<topic> 的时间线（依据材料覆盖 <start> 至 <end> [E1]）：
- 2024-03: <event1> [E1]
- 2024-07: <event2> [E2]
- 时间未定：<event3> [E3]
材料中未涵盖 <gap> 期间的情况。
"""

WEB_FACT_CHECK_TEMPLATE = """
Answer template for checking a claim against the evidence:

1. Restate the claim being checked in one sentence
2. A verdict -- supported / contradicted / not addressed by the evidence
3. The evidence for that verdict, each item cited
4. What would be needed to settle it, when the evidence does not

Citation rules:
- The verdict itself MUST rest on cited evidence; an uncited verdict is an opinion
- "Not addressed" is a real verdict and the correct one whenever the evidence is
  silent -- absence of evidence is never evidence of falsehood
- Web sources carry a publication date and a publisher; name them, because a
  reader checking a claim needs to weigh the source, not just the sentence:
  "<publisher>（<date>）报道 <fact> [E1]"
- When sources conflict, report the conflict rather than resolving it silently

Example structure:
待核查：<claim>
结论：<supported | contradicted | not addressed> [E1]
依据：<publisher>（<date>）指出 <evidence1> [E1]；<evidence2> [E2]
局限：<what the evidence cannot settle>
"""

INCIDENT_RESPONSE_TEMPLATE = """
Answer template for an incident response playbook:

1. Scope: what incident this covers and what it does not, cited
2. Phases, in order, with the actions under each cited:
   - 抑制 Containment: <action> [E1]
   - 根除 Eradication: <action> [E1]
   - 恢复 Recovery: <action> [E2]
3. Preconditions and decision points -- who authorizes what, cited
4. What the evidence does not cover, stated plainly

Citation rules:
- EVERY action MUST cite the source that prescribes it. An uncited step in a
  playbook is a step somebody may take during an incident on your say-so
- Do not fill a missing phase from general knowledge: name it as missing
  ("提供的材料未涵盖<phase>阶段") so the gap is visible before it is needed
- Preserve any ordering or authorization constraint the source states; dropping
  "only after X approves" turns a control into a suggestion
- Keep destructive actions (isolating hosts, revoking credentials, wiping) marked
  as the source marks them, including any reversibility note

Example structure:
<incident type> 处置流程（范围：<scope> [E1]）：
抑制：1. <action> [E1]  2. <action> [E1]
根除：1. <action> [E2]
恢复：1. <action> [E2]
决策点：<action> 需 <role> 批准 [E1]
材料未涵盖：<phase or condition>
"""

ATTACK_ANALYSIS_TEMPLATE = """
Answer template for analysing an attack:

1. What happened, in one cited sentence
2. The chain in order, each link cited:
   初始访问 → 立足 → 提权 → 横向移动 → 目标行动
   Include only the links the evidence supports; name the ones it does not
3. Indicators and affected assets, each cited
4. Confidence, and what it rests on

Citation rules:
- EVERY link in the chain MUST be cited. A chain is a causal claim, and an
  uncited link is the model inventing how the attacker got from one step to the
  next -- the most consequential kind of fabrication in this format
- Attribution requires an explicit source. Never infer an actor from technique
  overlap: "材料未指明攻击者" is the correct answer when it does not
- Keep an indicator exactly as written (hashes, addresses, paths); a
  reconstructed indicator is worse than none because it will be searched for
- Say which links are inferred versus stated, and hedge the inferred ones

Example structure:
事件概述：<summary> [E1]
攻击链：
- 初始访问：<technique> [E1]
- 提权：<technique> [E2]
- 横向移动：材料未涵盖
指标：<ioc1> [E2]
影响资产：<asset> [E1]
判断依据与置信度：<basis>；<links> 为推断
"""

DEFENSE_HARDENING_TEMPLATE = """
Answer template for defensive hardening recommendations:

1. What is being hardened and against what, cited
2. Recommendations ordered by the effect the evidence claims for them, each with:
   - the control [E1]
   - what it mitigates [E1]
   - its cost or operational impact, when the evidence states one
3. What the evidence does not let you recommend

Citation rules:
- EVERY recommendation MUST cite the source that supports it. Security advice
  invented by a model is advice with nobody behind it
- Order by evidence-stated impact, not by how well known a control is
- Carry the source's stated cost, downtime, or breakage risk with the control;
  a recommendation stripped of its cost reads as free and will be treated as free
- Do not generalise a control beyond the scope the source gives it (one version,
  one platform, one configuration)
- If the evidence supports nothing actionable, say so instead of reaching for
  generic best practice

Example structure:
加固目标：<asset> 针对 <threat> [E1]
建议：
1. <control> —— 缓解 <threat> [E1]；影响：<cost> [E1]
2. <control> —— 缓解 <threat> [E2]
材料不足以支持的方向：<gap>
"""

PDF_EXTRACTION_TEMPLATE = """
Answer template for reading content out of documents:

1. The requested content, reproduced faithfully, cited per passage
2. Structure preserved -- headings, list order, table rows as rows
3. Where in the document it came from (page or section), from the evidence
4. Anything requested that the excerpts do not contain

Citation rules:
- EVERY reproduced passage MUST carry its citation; extraction without
  provenance is indistinguishable from generation
- Reproduce, do not paraphrase. If the reader wanted a summary they would have
  asked for one, and a paraphrase silently drops the wording that mattered
- Never repair, complete, or reorder content. A truncated table stays truncated:
  "材料中该表格在此处截断" [E1]
- Keep numbers, units and identifiers exactly as written -- normalising them is
  the same fabrication as inventing them, only harder to notice
- When the excerpts do not contain what was asked for, say which part is absent
  rather than producing the nearest thing

Example structure:
<document> <section> 的内容 [E1]：
<verbatim excerpt> [E1]
<verbatim excerpt> [E2]
未包含在材料中的部分：<what is missing>
"""

SKILL_TEMPLATES: dict[str, str] = {
    "timeline_builder": TIMELINE_TEMPLATE,
    "web_fact_check": WEB_FACT_CHECK_TEMPLATE,
    "incident_response_playbook": INCIDENT_RESPONSE_TEMPLATE,
    "cyber_attack_analysis": ATTACK_ANALYSIS_TEMPLATE,
    "cyber_defense_hardening": DEFENSE_HARDENING_TEMPLATE,
    "pdf_text_reader": PDF_EXTRACTION_TEMPLATE,
}
"""Skills whose answer has a shape of its own."""

SKILL_QUERY_TYPES: dict[str, QueryType] = {
    "compare_entities": "comparison",
}
"""Skills that name a shape `templates.py` already describes. Mapping rather than
duplicating means the router's LLM choice reaches a template the keyword
inference would only have found if the question used one of its keywords."""

GENERAL_SKILLS: frozenset[str] = frozenset({SKILL_DEFAULT, "ai_knowledge_assistant"})
"""Skills that state no shape, so the question stays the best available signal."""


def skill_answer_template(skill: str, question: str) -> str:
    """Return the answer-shape guidance for a router-chosen skill.

    Falls back to question-based inference for a skill that names no shape and
    for an unrecognised one, so an unknown skill degrades to the behaviour that
    predates this module rather than to no guidance at all.
    """
    name = str(skill or "").strip() or SKILL_DEFAULT
    template = SKILL_TEMPLATES.get(name)
    if template is not None:
        return template
    query_type = SKILL_QUERY_TYPES.get(name)
    if query_type is not None:
        return get_answer_template(query_type)
    return get_answer_template(infer_query_type(question))


__all__ = [
    "ATTACK_ANALYSIS_TEMPLATE",
    "DEFENSE_HARDENING_TEMPLATE",
    "GENERAL_SKILLS",
    "INCIDENT_RESPONSE_TEMPLATE",
    "PDF_EXTRACTION_TEMPLATE",
    "SKILL_QUERY_TYPES",
    "SKILL_TEMPLATES",
    "TIMELINE_TEMPLATE",
    "WEB_FACT_CHECK_TEMPLATE",
    "skill_answer_template",
]
