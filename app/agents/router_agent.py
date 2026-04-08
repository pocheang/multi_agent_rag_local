import json
import re

from pydantic import BaseModel

from app.core.models import get_chat_model, get_reasoning_model
from app.services.agent_classifier import classify_agent_class, pick_cyber_skill
from app.services.query_intent import is_smalltalk_query


class RouteDecision(BaseModel):
    route: str
    reason: str
    skill: str
    agent_class: str


ROUTER_PROMPT = """
你是一个网络安全问答场景的 RAG 路由器。根据用户问题判断最合适的路线：
- vector: 适合从文档片段中找答案
- graph: 适合实体关系、依赖、组织结构、关联分析
- hybrid: 同时需要文档证据和关系图

同时选择一个 skill：
- answer_with_citations
- compare_entities
- timeline_builder
- web_fact_check
- cyber_attack_analysis
- cyber_defense_hardening
- incident_response_playbook
- ai_knowledge_assistant

路由建议：
- 提到漏洞利用、攻击链、横向移动、权限提升、C2，优先 cyber_attack_analysis
- 提到防护体系、检测规则、加固清单、零信任，优先 cyber_defense_hardening
- 提到告警处置、溯源、隔离、应急演练，优先 incident_response_playbook

只输出 JSON，格式：
{"route":"vector|graph|hybrid","reason":"...","skill":"..."}
"""


def _extract_json(text: str) -> dict:
    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if not match:
        return {"route": "vector", "reason": "fallback", "skill": "answer_with_citations"}
    try:
        return json.loads(match.group(0))
    except json.JSONDecodeError:
        return {"route": "vector", "reason": "fallback_json_error", "skill": "answer_with_citations"}


def decide_route(question: str, use_reasoning: bool = True) -> RouteDecision:
    agent_class = classify_agent_class(question)
    if is_smalltalk_query(question):
        return RouteDecision(
            route="vector",
            reason=f"smalltalk_local_only | agent_class={agent_class}",
            skill="answer_with_citations",
            agent_class=agent_class,
        )

    # Early skill selection for special agent classes
    if agent_class == "pdf_text":
        return RouteDecision(
            route="vector",
            reason=f"pdf_text_direct_route | agent_class={agent_class}",
            skill="pdf_text_reader",
            agent_class=agent_class,
        )

    try:
        model = get_reasoning_model() if use_reasoning else get_chat_model()
        result = model.invoke([("system", ROUTER_PROMPT), ("human", question)])
        text = result.content if hasattr(result, "content") else str(result)
        data = _extract_json(text)
    except Exception as e:
        data = {
            "route": "vector",
            "reason": f"router_invoke_error:{type(e).__name__}",
            "skill": "answer_with_citations",
        }

    route = data.get("route", "vector")
    if route not in {"vector", "graph", "hybrid"}:
        route = "vector"

    skill = data.get("skill", "answer_with_citations")
    if skill not in {
        "answer_with_citations",
        "compare_entities",
        "timeline_builder",
        "web_fact_check",
        "cyber_attack_analysis",
        "cyber_defense_hardening",
        "incident_response_playbook",
        "ai_knowledge_assistant",
        "pdf_text_reader",
    }:
        skill = "answer_with_citations"

    if agent_class == "cybersecurity":
        if skill not in {"cyber_attack_analysis", "cyber_defense_hardening", "incident_response_playbook"}:
            skill = pick_cyber_skill(question)
    elif agent_class == "artificial_intelligence":
        skill = "ai_knowledge_assistant"

    reason = f"{data.get('reason', 'fallback')} | agent_class={agent_class}"
    return RouteDecision(route=route, reason=reason, skill=skill, agent_class=agent_class)
