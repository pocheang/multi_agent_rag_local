import json
import logging
from typing import Any, Generator

from app.agents.graph_rag_agent import run_graph_rag
from app.agents.router_agent import decide_route
from app.agents.synthesis_agent import stream_synthesize_answer, synthesize_answer
from app.agents.vector_rag_agent import run_vector_rag
from app.agents.web_research_agent import run_web_research
from app.services.query_intent import is_smalltalk_query, should_force_web_research

logger = logging.getLogger(__name__)


def _safe_vector_result(question: str, allowed_sources: list[str] | None = None) -> dict[str, Any]:
    try:
        return run_vector_rag(question, allowed_sources=allowed_sources)
    except Exception as e:
        logger.exception(f"Vector RAG failed for question: {question}")
        return {"context": "", "citations": [], "retrieved_count": 0, "error": f"vector_error:{type(e).__name__}"}


def _safe_graph_result(question: str, allowed_sources: list[str] | None = None) -> dict[str, Any]:
    try:
        return run_graph_rag(question, allowed_sources=allowed_sources)
    except Exception as e:
        logger.exception(f"Graph RAG failed for question: {question}")
        return {"context": "", "entities": [], "neighbors": [], "error": f"graph_error:{type(e).__name__}"}


def _safe_web_result(question: str) -> dict[str, Any]:
    try:
        return run_web_research(question)
    except Exception as e:
        logger.exception(f"Web research failed for question: {question}")
        return {"used": False, "citations": [], "context": "", "error": f"web_error:{type(e).__name__}"}


def run_query_stream(
    question: str,
    use_web_fallback: bool = True,
    use_reasoning: bool = True,
    memory_context: str = "",
    allowed_sources: list[str] | None = None,
) -> Generator[dict[str, Any], None, dict[str, Any]]:
    state: dict[str, Any] = {
        "question": question,
        "memory_context": memory_context,
        "use_web_fallback": use_web_fallback,
        "use_reasoning": use_reasoning,
    }
    thoughts: list[str] = []

    yield {"type": "status", "message": "routing"}
    decision = decide_route(question, use_reasoning=use_reasoning)
    state.update({"route": decision.route, "reason": decision.reason, "skill": decision.skill, "agent_class": decision.agent_class})
    thoughts.append(f"路由结果: {decision.route}，skill={decision.skill}")
    thoughts.append(f"路由原因: {decision.reason}")
    yield {
        "type": "route",
        "route": decision.route,
        "reason": decision.reason,
        "skill": decision.skill,
        "agent_class": decision.agent_class,
    }
    yield {"type": "thought", "content": thoughts[-2]}
    yield {"type": "thought", "content": thoughts[-1]}

    route = decision.route

    if route in {"vector", "hybrid"}:
        yield {"type": "status", "message": "retrieving_vector"}
        state["vector_result"] = _safe_vector_result(question, allowed_sources=allowed_sources)
        if state["vector_result"].get("error"):
            thoughts.append(f"本地向量检索异常，已降级继续: {state['vector_result']['error']}")
            yield {"type": "thought", "content": thoughts[-1]}
        vector_count = state["vector_result"].get("retrieved_count", 0)
        thought = f"本地向量命中: {vector_count} 条。"
        thoughts.append(thought)
        yield {"type": "thought", "content": thought}
        yield {
            "type": "vector_result",
            "retrieved_count": vector_count,
        }

    if route in {"graph", "hybrid"}:
        yield {"type": "status", "message": "retrieving_graph"}
        state["graph_result"] = _safe_graph_result(question, allowed_sources=allowed_sources)
        if state["graph_result"].get("error"):
            thoughts.append(f"本地图谱检索异常，已降级继续: {state['graph_result']['error']}")
            yield {"type": "thought", "content": thoughts[-1]}
        entity_count = len(state["graph_result"].get("entities", []))
        thought = f"本地图谱实体命中: {entity_count} 个。"
        thoughts.append(thought)
        yield {"type": "thought", "content": thought}
        yield {
            "type": "graph_result",
            "entities": state["graph_result"].get("entities", []),
        }

    need_web = False
    force_web = should_force_web_research(question) or state.get("skill") == "web_fact_check"
    if is_smalltalk_query(question):
        need_web = False
        thoughts.append("检测到问候/闲聊，不触发联网检索。")
        yield {"type": "thought", "content": thoughts[-1]}
    elif use_web_fallback and force_web:
        need_web = True
        thoughts.append("检测到用户明确联网/时效性意图，优先触发联网补充。")
        yield {"type": "thought", "content": thoughts[-1]}
    elif route == "vector":
        need_web = state.get("vector_result", {}).get("retrieved_count", 0) < 2 and use_web_fallback
    elif route == "graph":
        need_web = not state.get("graph_result", {}).get("entities", []) and use_web_fallback
    elif route == "hybrid":
        need_web = state.get("vector_result", {}).get("retrieved_count", 0) < 2 and use_web_fallback

    if need_web:
        thoughts.append("本地证据不足，触发联网补充。")
        yield {"type": "thought", "content": thoughts[-1]}
        yield {"type": "status", "message": "retrieving_web"}
        state["web_result"] = _safe_web_result(question)
        if state["web_result"].get("error"):
            thoughts.append(f"联网补充异常，已降级继续: {state['web_result']['error']}")
            yield {"type": "thought", "content": thoughts[-1]}
        web_count = len(state["web_result"].get("citations", []))
        thoughts.append(f"联网补充命中: {web_count} 条。")
        yield {"type": "thought", "content": thoughts[-1]}
        yield {
            "type": "web_result",
            "used": state["web_result"].get("used", False),
            "count": web_count,
        }
    else:
        state.setdefault("web_result", {"used": False, "citations": [], "context": ""})
        if use_web_fallback:
            thoughts.append("本地证据充足，不触发联网。")
            yield {"type": "thought", "content": thoughts[-1]}
        else:
            thoughts.append("联网补充已关闭，仅使用本地证据。")
            yield {"type": "thought", "content": thoughts[-1]}

    yield {"type": "status", "message": "synthesizing"}
    thoughts.append("开始生成最终回答。")
    yield {"type": "thought", "content": thoughts[-1]}
    answer_parts: list[str] = []
    for chunk in stream_synthesize_answer(
        question=question,
        skill_name=state.get("skill", "answer_with_citations"),
        memory_context=state.get("memory_context", ""),
        vector_context=state.get("vector_result", {}).get("context", ""),
        graph_context=state.get("graph_result", {}).get("context", ""),
        web_context=state.get("web_result", {}).get("context", ""),
        use_reasoning=use_reasoning,
    ):
        answer_parts.append(chunk)
        yield {"type": "answer_chunk", "content": chunk}

    answer = "".join(answer_parts).strip()
    if not answer:
        answer = synthesize_answer(
            question=question,
            skill_name=state.get("skill", "answer_with_citations"),
            memory_context=state.get("memory_context", ""),
            vector_context=state.get("vector_result", {}).get("context", ""),
            graph_context=state.get("graph_result", {}).get("context", ""),
            web_context=state.get("web_result", {}).get("context", ""),
            use_reasoning=use_reasoning,
        )
        yield {"type": "answer_chunk", "content": answer}

    state["answer"] = answer
    final_payload = {
        "answer": answer,
        "route": state.get("route", "unknown"),
        "reason": state.get("reason", ""),
        "skill": state.get("skill", ""),
        "agent_class": state.get("agent_class", "general"),
        "vector_result": state.get("vector_result", {}),
        "graph_result": state.get("graph_result", {}),
        "web_result": state.get("web_result", {}),
        "thoughts": thoughts,
    }
    yield {"type": "done", "result": final_payload}
    return final_payload


def encode_sse(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
