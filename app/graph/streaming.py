import json
import logging
from concurrent.futures import TimeoutError as FutureTimeoutError
import time
from typing import Any, Generator

from app.agents.graph_rag_agent import run_graph_rag
from app.agents.router_agent import decide_route
from app.agents.synthesis_agent import stream_synthesize_answer, synthesize_answer
from app.agents.vector_rag_agent import run_vector_rag
from app.agents.web_research_agent import run_web_research
from app.services.adaptive_rag_policy import build_adaptive_plan
from app.services.answer_safety import sanitize_answer
from app.services.bulkhead import bulkhead
from app.services.citation_grounding import apply_sentence_grounding
from app.services.evidence_scoring import evidence_is_sufficient
from app.services.explainability import build_explainability_report
from app.services.hybrid_executor import HybridExecutorRejectedError, submit_hybrid
from app.services.query_intent import is_casual_chat_query, quick_smalltalk_reply, should_force_web_research
from app.services.request_context import deadline_exceeded, remaining_seconds
from app.services.retry_policy import call_with_retry
from app.services.resilience import call_with_circuit_breaker
from app.services.tracing import traced_span

logger = logging.getLogger(__name__)


def _safe_vector_result(
    question: str,
    allowed_sources: list[str] | None = None,
    retrieval_strategy: str | None = None,
) -> dict[str, Any]:
    try:
        with bulkhead("retrieval"):
            return call_with_retry(
                "stream.vector_rag",
                lambda: call_with_circuit_breaker(
                    "vector_rag.run",
                    lambda: run_vector_rag(
                        question,
                        allowed_sources=allowed_sources,
                        retrieval_strategy=retrieval_strategy,
                    )
                    if retrieval_strategy
                    else run_vector_rag(question, allowed_sources=allowed_sources),
                ),
            )
    except Exception as e:
        logger.exception(f"Vector RAG failed for question: {question}")
        return {"context": "", "citations": [], "retrieved_count": 0, "error": f"vector_error:{type(e).__name__}"}


def _safe_graph_result(question: str, allowed_sources: list[str] | None = None) -> dict[str, Any]:
    try:
        with bulkhead("neo4j"):
            return call_with_retry(
                "stream.graph_rag",
                lambda: call_with_circuit_breaker(
                    "graph_rag.run",
                    lambda: run_graph_rag(question, allowed_sources=allowed_sources),
                ),
            )
    except Exception as e:
        logger.exception(f"Graph RAG failed for question: {question}")
        return {"context": "", "entities": [], "neighbors": [], "error": f"graph_error:{type(e).__name__}"}


def _safe_web_result(question: str) -> dict[str, Any]:
    try:
        with bulkhead("web"):
            return call_with_retry(
                "stream.web_research",
                lambda: call_with_circuit_breaker("web_research.run", lambda: run_web_research(question)),
            )
    except Exception as e:
        logger.exception(f"Web research failed for question: {question}")
        return {"used": False, "citations": [], "context": "", "error": f"web_error:{type(e).__name__}"}


def run_query_stream(
    question: str,
    use_web_fallback: bool = False,
    use_reasoning: bool = False,
    memory_context: str = "",
    allowed_sources: list[str] | None = None,
    agent_class_hint: str | None = None,
    retrieval_strategy: str | None = None,
) -> Generator[dict[str, Any], None, dict[str, Any]]:
    state: dict[str, Any] = {
        "question": question,
        "memory_context": memory_context,
        "use_web_fallback": use_web_fallback,
        "use_reasoning": use_reasoning,
        "retrieval_strategy": retrieval_strategy,
    }
    thoughts: list[str] = []

    if deadline_exceeded():
        timeout_payload = {
            "answer": "请求超时，请缩小问题范围后重试。",
            "route": "unknown",
            "reason": "deadline_exceeded_before_start",
            "skill": "",
            "agent_class": "general",
            "vector_result": {},
            "graph_result": {},
            "web_result": {"used": False, "citations": [], "context": ""},
            "grounding": {},
            "answer_safety": {},
            "explainability": {},
            "thoughts": ["执行前已超出请求超时预算。"],
        }
        yield {"type": "done", "result": timeout_payload}
        return timeout_payload

    yield {"type": "status", "message": "routing"}
    if agent_class_hint:
        decision = decide_route(question, use_reasoning=use_reasoning, agent_class_hint=agent_class_hint)
    else:
        decision = decide_route(question, use_reasoning=use_reasoning)
    force_web = should_force_web_research(question) or decision.skill == "web_fact_check"
    plan = build_adaptive_plan(
        question=question,
        initial_route=decision.route,
        skill=decision.skill,
        use_web_fallback=use_web_fallback,
        force_web=force_web,
    )
    state.update(
        {
            "route": plan.route,
            "reason": f"{decision.reason} | {plan.reason}",
            "skill": decision.skill,
            "agent_class": decision.agent_class,
            "adaptive_level": plan.level,
            "adaptive_min_vector_hits": plan.min_vector_hits,
            "adaptive_prefer_graph": plan.prefer_graph,
            "adaptive_prefer_web": plan.prefer_web,
        }
    )
    thoughts.append(f"[理解阶段] 路由结果: {plan.route}，skill={decision.skill}")
    thoughts.append(f"[理解阶段] 路由原因: {state['reason']}")
    yield {
        "type": "route",
        "route": state.get("route", "vector"),
        "reason": state.get("reason", ""),
        "skill": decision.skill,
        "agent_class": decision.agent_class,
        "adaptive_level": plan.level,
    }
    yield {"type": "thought", "content": thoughts[-2]}
    yield {"type": "thought", "content": thoughts[-1]}

    route = state.get("route", decision.route)
    casual_chat = is_casual_chat_query(question)
    did_parallel_hybrid = False

    if casual_chat:
        state["route"] = "smalltalk_fast"
        state["reason"] = "smalltalk_fast_path"
        state["skill"] = "smalltalk"
        state["vector_result"] = {"context": "", "citations": [], "retrieved_count": 0}
        state["graph_result"] = {"context": "", "entities": [], "neighbors": []}
        state["web_result"] = {"used": False, "citations": [], "context": ""}
        thoughts.append("[执行阶段] 检测到问候/日常闲聊，跳过检索与引用，仅进行自然对话回复。")
        yield {"type": "thought", "content": thoughts[-1]}

        # Early return for casual chat - skip all retrieval and web logic
        yield {"type": "status", "message": "smalltalk_fast"}
        answer = quick_smalltalk_reply(question) or "你好，我在。"
        yield {"type": "answer_chunk", "content": answer}
        state["answer"] = answer
        state["grounding"] = {"checked": False, "reason": "smalltalk_fast_path"}
        state["answer_safety"] = {}
        explainability = build_explainability_report(state)
        final_payload = {
            "answer": answer,
            "route": "smalltalk_fast",
            "reason": "smalltalk_fast_path",
            "skill": "smalltalk",
            "agent_class": state.get("agent_class", "general"),
            "vector_result": state.get("vector_result", {}),
            "graph_result": state.get("graph_result", {}),
            "web_result": state.get("web_result", {}),
            "grounding": state["grounding"],
            "answer_safety": state["answer_safety"],
            "explainability": explainability,
            "thoughts": thoughts,
        }
        yield {"type": "done", "result": final_payload}
        return final_payload

    if (not casual_chat) and route == "hybrid" and (not deadline_exceeded()):
        did_parallel_hybrid = True
        yield {"type": "status", "message": "retrieving_hybrid_parallel"}
        timeout_s = remaining_seconds()
        if timeout_s is None:
            timeout_s = 15.0
        timeout_s = max(0.1, float(timeout_s))
        deadline = time.monotonic() + timeout_s
        fut_vector = None
        fut_graph = None
        vector_result = {"context": "", "citations": [], "retrieved_count": 0, "error": "vector_error:Timeout"}
        graph_result = {"context": "", "entities": [], "neighbors": [], "error": "graph_error:Timeout"}
        try:
            fut_vector = submit_hybrid(_safe_vector_result, question, allowed_sources, retrieval_strategy)
            fut_graph = submit_hybrid(_safe_graph_result, question, allowed_sources)
            try:
                left = max(0.1, deadline - time.monotonic())
                vector_result = fut_vector.result(timeout=left)
            except FutureTimeoutError:
                fut_vector.cancel()
            except Exception as e:
                logger.exception(f"Vector RAG failed in streaming for question: {question}")
                vector_result = {"context": "", "citations": [], "retrieved_count": 0, "error": f"vector_error:{type(e).__name__}"}
            state["vector_result"] = vector_result
            try:
                left = max(0.1, deadline - time.monotonic())
                graph_result = fut_graph.result(timeout=left)
            except FutureTimeoutError:
                fut_graph.cancel()
            except Exception as e:
                logger.exception(f"Graph RAG failed in streaming for question: {question}")
                graph_result = {"context": "", "entities": [], "neighbors": [], "error": f"graph_error:{type(e).__name__}"}
            state["graph_result"] = graph_result
        except HybridExecutorRejectedError:
            if fut_vector is not None:
                fut_vector.cancel()
            if fut_graph is not None:
                fut_graph.cancel()
            state["vector_result"] = {
                "context": "",
                "citations": [],
                "retrieved_count": 0,
                "error": "vector_error:Overloaded",
            }
            state["graph_result"] = {
                "context": "",
                "entities": [],
                "neighbors": [],
                "error": "graph_error:Overloaded",
            }

        if state["vector_result"].get("error"):
            thoughts.append(f"本地向量检索异常，已降级继续: {state['vector_result']['error']}")
            yield {"type": "thought", "content": thoughts[-1]}
        vector_count = state["vector_result"].get("retrieved_count", 0)
        retrieval_diag = state["vector_result"].get("retrieval_diagnostics", {}) or {}
        if retrieval_diag.get("degraded_to_relaxed_threshold"):
            thoughts.append("[执行阶段] 严格阈值召回为空，已自动放宽阈值重试。")
            yield {"type": "thought", "content": thoughts[-1]}
        thoughts.append(f"[执行阶段] 本地向量命中: {vector_count} 条。")
        yield {"type": "thought", "content": thoughts[-1]}
        yield {
            "type": "vector_result",
            "retrieved_count": vector_count,
            "diagnostics": {
                "rewrites": retrieval_diag.get("rewrites", []),
                "degraded_to_relaxed_threshold": retrieval_diag.get("degraded_to_relaxed_threshold", False),
                "vector_hits_by_rewrite": retrieval_diag.get("vector_hits_by_rewrite", {}),
                "bm25_hits_by_rewrite": retrieval_diag.get("bm25_hits_by_rewrite", {}),
            },
        }

        if state["graph_result"].get("error"):
            thoughts.append(f"本地图谱检索异常，已降级继续: {state['graph_result']['error']}")
            yield {"type": "thought", "content": thoughts[-1]}
        entity_count = len(state["graph_result"].get("entities", []))
        neighbor_count = len(state["graph_result"].get("neighbors", []))
        path_count = len(state["graph_result"].get("paths", []))
        thoughts.append(f"[执行阶段] 本地图谱命中: {entity_count} 个实体, {neighbor_count} 个邻居关系, {path_count} 条路径。")
        yield {"type": "thought", "content": thoughts[-1]}
        yield {
            "type": "graph_result",
            "entities": state["graph_result"].get("entities", []),
            "neighbors": state["graph_result"].get("neighbors", []),
            "paths": state["graph_result"].get("paths", []),
            "context": state["graph_result"].get("context", ""),
        }

    if (not casual_chat) and route in {"vector", "hybrid"} and (not did_parallel_hybrid) and (not deadline_exceeded()):
        yield {"type": "status", "message": "retrieving_vector"}
        with traced_span("streaming.vector_retrieval", {"strategy": str(retrieval_strategy or "default")}):
            state["vector_result"] = _safe_vector_result(
                question,
                allowed_sources=allowed_sources,
                retrieval_strategy=retrieval_strategy,
            )
        if state["vector_result"].get("error"):
            thoughts.append(f"本地向量检索异常，已降级继续: {state['vector_result']['error']}")
            yield {"type": "thought", "content": thoughts[-1]}
        vector_count = state["vector_result"].get("retrieved_count", 0)
        retrieval_diag = state["vector_result"].get("retrieval_diagnostics", {}) or {}
        if retrieval_diag.get("degraded_to_relaxed_threshold"):
            thoughts.append("[执行阶段] 严格阈值召回为空，已自动放宽阈值重试。")
            yield {"type": "thought", "content": thoughts[-1]}
        thought = f"[执行阶段] 本地向量命中: {vector_count} 条。"
        thoughts.append(thought)
        yield {"type": "thought", "content": thought}
        yield {
            "type": "vector_result",
            "retrieved_count": vector_count,
            "diagnostics": {
                "rewrites": retrieval_diag.get("rewrites", []),
                "degraded_to_relaxed_threshold": retrieval_diag.get("degraded_to_relaxed_threshold", False),
                "vector_hits_by_rewrite": retrieval_diag.get("vector_hits_by_rewrite", {}),
                "bm25_hits_by_rewrite": retrieval_diag.get("bm25_hits_by_rewrite", {}),
            },
        }

    if (not casual_chat) and route in {"graph", "hybrid"} and (not did_parallel_hybrid) and (not deadline_exceeded()):
        yield {"type": "status", "message": "retrieving_graph"}
        state["graph_result"] = _safe_graph_result(question, allowed_sources=allowed_sources)
        if state["graph_result"].get("error"):
            thoughts.append(f"本地图谱检索异常，已降级继续: {state['graph_result']['error']}")
            yield {"type": "thought", "content": thoughts[-1]}
        entity_count = len(state["graph_result"].get("entities", []))
        neighbor_count = len(state["graph_result"].get("neighbors", []))
        path_count = len(state["graph_result"].get("paths", []))
        thought = f"[执行阶段] 本地图谱命中: {entity_count} 个实体, {neighbor_count} 个邻居关系, {path_count} 条路径。"
        thoughts.append(thought)
        yield {"type": "thought", "content": thought}
        yield {
            "type": "graph_result",
            "entities": state["graph_result"].get("entities", []),
            "neighbors": state["graph_result"].get("neighbors", []),
            "paths": state["graph_result"].get("paths", []),
            "context": state["graph_result"].get("context", ""),
        }

    need_web = False
    force_web = bool(state.get("adaptive_prefer_web", False))
    if casual_chat:
        need_web = False
    elif force_web:
        # User explicitly enabled web or query has time-sensitive intent
        need_web = True
        thoughts.append("[执行阶段] 用户开启联网增强或检测到时效性意图，强制触发联网补充。")
        yield {"type": "thought", "content": thoughts[-1]}
    elif route == "vector":
        min_hits = int(state.get("adaptive_min_vector_hits", 2) or 2)
        vector_result = state.get("vector_result")
        if vector_result:
            need_web = (not evidence_is_sufficient(vector_result, {}, route="vector", min_hits=min_hits)) and use_web_fallback
        else:
            need_web = use_web_fallback
    elif route == "graph":
        min_hits = int(state.get("adaptive_min_vector_hits", 2) or 2)
        graph_result = state.get("graph_result")
        if graph_result:
            need_web = (
                not evidence_is_sufficient({}, graph_result, route="graph", min_hits=min_hits)
                and use_web_fallback
            )
        else:
            need_web = use_web_fallback
    elif route == "hybrid":
        min_hits = int(state.get("adaptive_min_vector_hits", 2) or 2)
        vector_result = state.get("vector_result")
        graph_result = state.get("graph_result")
        if vector_result or graph_result:
            need_web = (
                not evidence_is_sufficient(
                    vector_result or {},
                    graph_result or {},
                    route="hybrid",
                    min_hits=min_hits,
                )
                and use_web_fallback
            )
        else:
            need_web = use_web_fallback

    if deadline_exceeded():
        state.setdefault("web_result", {"used": False, "citations": [], "context": ""})
        thoughts.append("[执行阶段] 已达到请求超时预算，跳过后续联网补充。")
        yield {"type": "thought", "content": thoughts[-1]}
    elif need_web:
        thoughts.append("[执行阶段] 本地证据不足，触发联网补充。")
        yield {"type": "thought", "content": thoughts[-1]}
        yield {"type": "status", "message": "retrieving_web"}
        state["web_result"] = _safe_web_result(question)
        if state["web_result"].get("error"):
            thoughts.append(f"联网补充异常，已降级继续: {state['web_result']['error']}")
            yield {"type": "thought", "content": thoughts[-1]}
        web_count = len(state["web_result"].get("citations", []))
        thoughts.append(f"[执行阶段] 联网补充命中: {web_count} 条。")
        yield {"type": "thought", "content": thoughts[-1]}
        yield {
            "type": "web_result",
            "used": state["web_result"].get("used", False),
            "count": web_count,
        }
    else:
        state.setdefault("web_result", {"used": False, "citations": [], "context": ""})
        if use_web_fallback:
            thoughts.append("[执行阶段] 本地证据充足，不触发联网。")
            yield {"type": "thought", "content": thoughts[-1]}
        else:
            thoughts.append("[执行阶段] 联网补充已关闭，仅使用本地证据。")
            yield {"type": "thought", "content": thoughts[-1]}

    yield {"type": "status", "message": "synthesizing"}
    thoughts.append("[校验与回复阶段] 开始生成并校验最终回答。")
    yield {"type": "thought", "content": thoughts[-1]}
    answer_parts: list[str] = []
    stream_had_chunks = False
    stream_failed = False
    try:
        for chunk_event in stream_synthesize_answer(
            question=question,
            skill_name=state.get("skill", "answer_with_citations"),
            memory_context=state.get("memory_context", ""),
            vector_context=state.get("vector_result", {}).get("context", ""),
            graph_context=state.get("graph_result", {}).get("context", ""),
            web_context=state.get("web_result", {}).get("context", ""),
            use_reasoning=use_reasoning,
        ):
            if not isinstance(chunk_event, dict):
                text = str(chunk_event)
                answer_parts.append(text)
                stream_had_chunks = True
                yield {"type": "answer_chunk", "content": text}
                continue
            event_type = str(chunk_event.get("type", "chunk") or "chunk").strip().lower()
            content = str(chunk_event.get("content", "") or "")
            if not content:
                continue
            if event_type == "reset":
                answer_parts = [content]
                if stream_had_chunks:
                    yield {"type": "answer_reset", "content": content}
                else:
                    stream_had_chunks = True
                    yield {"type": "answer_chunk", "content": content}
            else:
                answer_parts.append(content)
                stream_had_chunks = True
                yield {"type": "answer_chunk", "content": content}
    except Exception as e:
        logger.exception(f"Streaming synthesis crashed for question: {question}")
        stream_failed = True
        answer_parts = []  # Clear potentially corrupted partial answer
        thoughts.append(f"生成阶段异常，已降级返回兜底答案: {type(e).__name__}")
        yield {"type": "thought", "content": thoughts[-1]}

    answer = "".join(answer_parts).strip()
    if stream_failed or (not answer):
        try:
            answer = synthesize_answer(
                question=question,
                skill_name=state.get("skill", "answer_with_citations"),
                memory_context=state.get("memory_context", ""),
                vector_context=state.get("vector_result", {}).get("context", ""),
                graph_context=state.get("graph_result", {}).get("context", ""),
                web_context=state.get("web_result", {}).get("context", ""),
                use_reasoning=use_reasoning,
            )
        except Exception as e:
            logger.exception(f"Fallback synthesis crashed for question: {question}")
            thoughts.append(f"兜底生成也异常: {type(e).__name__}")
            yield {"type": "thought", "content": thoughts[-1]}
            answer = "抱歉，当前答案生成服务暂时不可用。请稍后重试，或先缩小问题范围后再试。"
        if stream_had_chunks:
            yield {"type": "answer_reset", "content": answer}
        else:
            yield {"type": "answer_chunk", "content": answer}

    evidence_texts = []
    for c in state.get("vector_result", {}).get("citations", []) or []:
        evidence_texts.append(str(c.get("content", "")))
    for c in state.get("web_result", {}).get("citations", []) or []:
        evidence_texts.append(str(c.get("content", "")))
    evidence_texts.append(state.get("graph_result", {}).get("context", ""))
    grounded_answer, grounding_report = apply_sentence_grounding(answer=answer, evidence_texts=evidence_texts)
    safe_answer, safety_report = sanitize_answer(grounded_answer)

    if safe_answer != answer:
        yield {"type": "answer_reset", "content": safe_answer}
    state["answer"] = safe_answer
    state["grounding"] = grounding_report
    state["answer_safety"] = safety_report
    explainability = build_explainability_report(state)
    final_payload = {
        "answer": safe_answer,
        "route": state.get("route", "unknown"),
        "reason": state.get("reason", ""),
        "skill": state.get("skill", ""),
        "agent_class": state.get("agent_class", "general"),
        "vector_result": state.get("vector_result", {}),
        "graph_result": state.get("graph_result", {}),
        "web_result": state.get("web_result", {}),
        "grounding": grounding_report,
        "answer_safety": safety_report,
        "explainability": explainability,
        "thoughts": thoughts,
    }
    yield {"type": "done", "result": final_payload}
    return final_payload


def encode_sse(data: dict[str, Any]) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"
