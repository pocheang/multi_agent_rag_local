import asyncio
import json
import logging
import re
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence
from typing import Any

from app.agents.synthesizer.citations import (
    citation_labels_from_contexts,
    normalize_answer_citations,
)
from app.agents.synthesizer.skills import skill_answer_template
from app.agents.synthesizer.templates import (
    get_cot_reasoning_prompt,
)
from app.agents.validation.public import verify_generated_answer
from app.core.config import get_settings
from app.prompts.core.canonical_agent_prompts import (
    ANSWER_PROMPT,
    NO_EVIDENCE_ANSWER_PROMPT,
    NO_EVIDENCE_REVIEW_PROMPT,
    REVIEW_PROMPT,
)
from app.services.language.analytics import LanguageAnalytics
from app.services.language.detector import detect_language
from app.services.models.runtime import get_chat_model, get_reasoning_model
from app.services.observability.log_safety import question_ref
from app.services.query.intent import is_casual_chat_query
from app.services.runtime.bulkhead import bulkhead
from app.services.runtime.request_context import deadline_exceeded, overload_mode_enabled

logger = logging.getLogger(__name__)


class _NoSourceDocuments(Exception):
    """Verification has nothing to verify against; skip it rather than pass it."""


__all__ = [
    "SYNTHESIS_FALLBACK_MESSAGE",
    "CASUAL_CHAT_HIGH_TEMPERATURE",
    "SIMILARITY_STOP_THRESHOLD",
    "ANSWER_PROMPT",
    "NO_EVIDENCE_ANSWER_PROMPT",
    "NO_EVIDENCE_REVIEW_PROMPT",
    "REVIEW_PROMPT",
    "synthesize_answer",
    "stream_synthesize_answer",
]

SYNTHESIS_FALLBACK_MESSAGE = "抱歉，当前答案生成服务暂时不可用。请稍后重试，或先缩小问题范围后再试。"
CASUAL_CHAT_HIGH_TEMPERATURE = 0.9
SIMILARITY_STOP_THRESHOLD = 0.92


_TOKEN_RE = re.compile(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]")


# `_parse_source_docs_from_contexts` used to live here: it reconstructed
# structured source documents by regexing `[doc_id:page] content` back out of the
# rendered context string. That form was retired when ContextBuilder moved to
# `[E{k}] document=...`, so the regex matched nothing and fact verification --
# whenever it was switched on -- verified an answer against an empty source list
# and reported perfect groundedness. Callers now hand the structured evidence
# straight through; a text round trip was never the right shape for data the
# caller already had.


def _build_prompt_with_language(
    question: str,
    detected_language: str,
    skill_name: str,
    memory_context: str = "",
    vector_context: str = "",
    graph_context: str = "",
    web_context: str = "",
    include_evidence_guidance: bool = True,
) -> str:
    """Build prompt with language hint and query-type-specific template for multilingual support."""
    language_hint = f"[Language: {detected_language}]\n"

    template_section = ""
    if include_evidence_guidance:
        # The skill selects the shape; it falls back to inferring one from the
        # question for the skills that name none. One block, not two -- see
        # app/agents/synthesizer/skills.py.
        answer_template = skill_answer_template(skill_name, question)
        cot_prompt = get_cot_reasoning_prompt()
        template_section = f"\n答案模板指导（Skill: {skill_name}）：\n{answer_template}\n\n{cot_prompt}\n"

    return (
        f"{language_hint}"
        f"技能: {skill_name}\n\n"
        f"用户问题:\n{question}\n\n"
        f"记忆上下文:\n{memory_context or '无'}\n\n"
        f"向量检索上下文:\n{vector_context or '无'}\n\n"
        f"图谱上下文:\n{graph_context or '无'}\n\n"
        f"联网补充上下文:\n{web_context or '无'}\n"
        f"{template_section}"
    )


def _evidence_generation_prompt(allowed_labels: Collection[str]) -> str:
    markers = ", ".join(f"[{label}]" for label in sorted(allowed_labels))
    return (
        f"{ANSWER_PROMPT}\n\n"
        "Allowed citation markers from retrieved evidence: "
        f"{markers}. Use only these exact markers; never invent citation markers."
    )


def _evidence_review_prompt(allowed_labels: Collection[str]) -> str:
    markers = ", ".join(f"[{label}]" for label in sorted(allowed_labels))
    return (
        f"{REVIEW_PROMPT}\n\n"
        "Allowed citation markers from retrieved evidence: "
        f"{markers}. Preserve only these exact markers and remove invented markers."
    )


def _stream_content(model, system_prompt: str, prompt: str, on_token: Callable[[str], None]) -> str:
    """Collect a streamed generation, handing each fragment to the caller.

    Falls back to a single invoke if the provider cannot stream: a model without
    streaming support should still produce an answer, just without the live view.
    """
    parts: list[str] = []
    try:
        for chunk in model.stream([("system", system_prompt), ("human", prompt)]):
            text = str(getattr(chunk, "content", "") or "")
            if text:
                parts.append(text)
                on_token(text)
    except Exception as exc:
        logger.warning("streaming generation unavailable, falling back to invoke: %s", type(exc).__name__)
        parts.clear()
    if parts:
        return "".join(parts)
    result = model.invoke([("system", system_prompt), ("human", prompt)])
    return str(result.content if hasattr(result, "content") else result)


def _build_generation_model(use_reasoning: bool, question: str):
    temp_override = CASUAL_CHAT_HIGH_TEMPERATURE if is_casual_chat_query(question) else None
    if use_reasoning:
        try:
            return get_reasoning_model(temperature=temp_override)
        except TypeError:
            return get_reasoning_model()
    try:
        return get_chat_model(temperature=temp_override)
    except TypeError:
        return get_chat_model()


def _build_review_model(use_reasoning: bool):
    if use_reasoning:
        try:
            return get_reasoning_model(temperature=0)
        except TypeError:
            return get_reasoning_model()
    try:
        return get_chat_model(temperature=0)
    except TypeError:
        return get_chat_model()


def _extract_json(text: str) -> dict:
    raw = str(text or "").strip()
    match = re.search(r"\{.*\}", raw, flags=re.DOTALL)
    if not match:
        return {}
    try:
        data = json.loads(match.group(0))
    except (json.JSONDecodeError, ValueError) as e:
        logger.debug(f"Failed to parse JSON: {e}")
        return {}
    return data if isinstance(data, dict) else {}


def _similarity(a: str, b: str) -> float:
    ta = set(_TOKEN_RE.findall((a or "").lower()))
    tb = set(_TOKEN_RE.findall((b or "").lower()))
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta | tb))


def _review_once(
    question: str,
    candidate_answer: str,
    memory_context: str,
    vector_context: str,
    graph_context: str,
    web_context: str,
    use_reasoning: bool,
    allowed_labels: Collection[str],
) -> tuple[bool, str, list[str], str]:
    if deadline_exceeded():
        return True, candidate_answer, [], "deadline_exceeded"
    payload = (
        f"用户问题:\n{question}\n\n"
        f"记忆上下文:\n{memory_context or '无'}\n\n"
        f"向量上下文:\n{vector_context or '无'}\n\n"
        f"图谱上下文:\n{graph_context or '无'}\n\n"
        f"联网上下文:\n{web_context or '无'}\n\n"
        f"当前答案:\n{candidate_answer}\n"
    )
    try:
        with bulkhead("llm"):
            model = _build_review_model(use_reasoning=use_reasoning)
            review_prompt = _evidence_review_prompt(allowed_labels) if allowed_labels else NO_EVIDENCE_REVIEW_PROMPT
            result = model.invoke([("system", review_prompt), ("human", payload)])
        data = _extract_json(result.content if hasattr(result, "content") else str(result))
    except Exception as e:
        return True, candidate_answer, [], f"review_unavailable:{type(e).__name__}"

    is_correct = bool(data.get("is_correct", False))
    analysis = str(data.get("analysis", "") or "")
    improved = str(data.get("improved_answer", "") or "").strip() or candidate_answer
    raw_issues = data.get("issues", [])
    issues = [str(x).strip() for x in raw_issues] if isinstance(raw_issues, list) else []
    issues = [x for x in issues if x]
    return is_correct, improved, issues[:3], analysis


def _refine_answer(
    question: str,
    initial_answer: str,
    memory_context: str,
    vector_context: str,
    graph_context: str,
    web_context: str,
    use_reasoning: bool,
    allowed_labels: Collection[str],
) -> str:
    answer = (initial_answer or "").strip()
    if not answer:
        return SYNTHESIS_FALLBACK_MESSAGE

    settings = get_settings()
    # A review is a strict-quality opt-in and must never turn into an
    # unbounded self-review loop. The pipeline budget permits at most one
    # model-assisted review/regeneration per request.
    max_rounds = min(1, int(getattr(settings, "synthesis_refine_max_rounds", 1) or 1))
    if overload_mode_enabled():
        max_rounds = min(max_rounds, int(getattr(settings, "synthesis_refine_overload_rounds", 1) or 1))
    max_rounds = max(0, max_rounds)
    if max_rounds == 0:
        return answer

    prev = answer
    for _i in range(1, max_rounds + 1):
        if deadline_exceeded():
            return prev
        is_correct, improved, _issues, _analysis = _review_once(
            question=question,
            candidate_answer=prev,
            memory_context=memory_context,
            vector_context=vector_context,
            graph_context=graph_context,
            web_context=web_context,
            use_reasoning=use_reasoning,
            allowed_labels=allowed_labels,
        )
        improved = (improved or "").strip() or prev
        if is_correct:
            return improved
        if _similarity(prev, improved) >= SIMILARITY_STOP_THRESHOLD:
            return improved
        prev = improved

    return prev


def _self_review_enabled(enable_self_review: bool | None) -> bool:
    """Return whether the optional LLM self-review pass is enabled.

    Self-review is explicit-opt-in only; there is no profile-based default.
    """
    return bool(enable_self_review)


def synthesize_answer(
    question: str,
    skill_name: str,
    memory_context: str = "",
    vector_context: str = "",
    graph_context: str = "",
    web_context: str = "",
    use_reasoning: bool = False,
    force_language: str = "",
    session_id: str = "",
    enable_fact_verification: bool = True,
    enable_self_review: bool | None = None,
    source_documents: Sequence[Mapping[str, Any]] | None = None,
    on_token: Callable[[str], None] | None = None,
) -> dict:
    """
    Synthesize answer with language detection and fact verification support.

    Args:
        question: User question
        skill_name: Skill name for context
        memory_context: Memory context
        vector_context: Vector retrieval context
        graph_context: Graph context
        web_context: Web search context
        use_reasoning: Whether to use reasoning model
        force_language: Force specific language ('zh' or 'en'), empty string for auto-detect
        session_id: Session identifier for analytics
        enable_fact_verification: Enable post-generation fact verification (Task 14)
        source_documents: Structured evidence for fact verification. Required for
            it to mean anything: without it there is nothing to verify against.
        on_token: Called with each generated fragment. The caller is responsible
            for redacting before showing anything -- see app/privacy/streaming.py.
        enable_self_review: Explicit review-policy override; self-review is
            opt-in only and capped at one round.

    Returns:
        dict with 'answer', 'detected_language', and optional 'verification' keys
    """
    # Detect language (or use forced language)
    detected_language = force_language if force_language else detect_language(question)

    # Log language detection for analytics
    try:
        analytics = LanguageAnalytics.get_instance()
        analytics.log_detection(
            query=question,
            detected_language=detected_language,
            force_language=force_language,
            session_id=session_id,
        )
    except Exception as e:
        logger.warning(f"Failed to log language analytics: {e}")

    allowed_labels = citation_labels_from_contexts(vector_context, graph_context, web_context)

    # Build prompt with language hint
    prompt = _build_prompt_with_language(
        question=question,
        detected_language=detected_language,
        skill_name=skill_name,
        memory_context=memory_context,
        vector_context=vector_context,
        graph_context=graph_context,
        web_context=web_context,
        include_evidence_guidance=bool(allowed_labels),
    )
    system_prompt = _evidence_generation_prompt(allowed_labels) if allowed_labels else NO_EVIDENCE_ANSWER_PROMPT

    try:
        with bulkhead("llm"):
            model = _build_generation_model(use_reasoning=use_reasoning, question=question)
            if on_token is None:
                result = model.invoke([("system", system_prompt), ("human", prompt)])
                content = result.content if hasattr(result, "content") else str(result)
            else:
                content = _stream_content(model, system_prompt, prompt, on_token)
        initial = str(content).strip()
        if not initial:
            return {
                "answer": SYNTHESIS_FALLBACK_MESSAGE,
                "detected_language": detected_language,
            }
        final_answer = initial
        if _self_review_enabled(enable_self_review):
            final_answer = _refine_answer(
                question=question,
                initial_answer=initial,
                memory_context=memory_context,
                vector_context=vector_context,
                graph_context=graph_context,
                web_context=web_context,
                use_reasoning=use_reasoning,
                allowed_labels=allowed_labels,
            )
        final_answer = normalize_answer_citations(final_answer, allowed_labels)
        if not final_answer:
            final_answer = SYNTHESIS_FALLBACK_MESSAGE

        # Task 14: Post-generation fact verification
        verification_result = None
        if enable_fact_verification and final_answer != SYNTHESIS_FALLBACK_MESSAGE:
            try:
                source_docs = list(source_documents or ())
                if not source_docs:
                    logger.info("Skipping fact verification: no structured source documents were supplied")
                    raise _NoSourceDocuments

                # ``synthesize_answer`` is synchronous. An async caller
                # already owns the event loop, so nesting ``asyncio.run``
                # cannot execute verification and previously leaked an
                # un-awaited coroutine. Keep the answer path non-blocking and
                # record an explicit local degradation instead.
                try:
                    asyncio.get_running_loop()
                except RuntimeError:
                    verification_result = asyncio.run(verify_generated_answer(final_answer, source_docs))
                else:
                    logger.info("Skipping synchronous fact verification inside an active event loop")

                if verification_result is not None:
                    logger.info(
                        f"Fact verification: groundedness={verification_result.groundedness_score:.2f}, "
                        f"verified={len(verification_result.verified_claims)}, "
                        f"unverified={len(verification_result.unverified_claims)}"
                    )

                    # If groundedness is too low, flag for review
                    if verification_result.groundedness_score < 0.80:
                        logger.warning(
                            f"Low groundedness score: {verification_result.groundedness_score:.2f}. "
                            f"Issues: {verification_result.issues[:3]}"
                        )

            except _NoSourceDocuments:
                verification_result = None
            except Exception as e:
                logger.warning(f"Fact verification failed: {e}")
                verification_result = None

        result_dict = {
            "answer": final_answer,
            "detected_language": detected_language,
        }

        # Include verification result if available
        if verification_result:
            result_dict["verification"] = {
                "groundedness_score": verification_result.groundedness_score,
                "overall_verified": verification_result.overall_verified,
                "unverified_count": len(verification_result.unverified_claims),
                "issues": verification_result.issues[:5],  # Top 5 issues
            }

        return result_dict

    except (RuntimeError, ValueError):
        logger.exception("Synthesis failed")
        return {
            "answer": SYNTHESIS_FALLBACK_MESSAGE,
            "detected_language": detected_language,
        }
    except Exception as e:
        logger.exception(f"Unexpected error in synthesis: {e}")
        return {
            "answer": SYNTHESIS_FALLBACK_MESSAGE,
            "detected_language": detected_language,
        }


def stream_synthesize_answer(
    question: str,
    skill_name: str,
    memory_context: str = "",
    vector_context: str = "",
    graph_context: str = "",
    web_context: str = "",
    use_reasoning: bool = False,
    force_language: str = "",
    session_id: str = "",
    enable_self_review: bool | None = None,
) -> Iterable[dict[str, str] | str]:
    """
    Stream synthesize answer with language detection support.

    Args:
        question: User question
        skill_name: Skill name for context
        memory_context: Memory context
        vector_context: Vector retrieval context
        graph_context: Graph context
        web_context: Web search context
        use_reasoning: Whether to use reasoning model
        force_language: Force specific language ('zh' or 'en'), empty string for auto-detect
        session_id: Session identifier for analytics
        enable_self_review: Explicit self-review-policy override.

    Yields:
        Text chunks or dict with metadata
    """
    # Detect language (or use forced language)
    detected_language = force_language if force_language else detect_language(question)
    logger.info(f"Streaming synthesis language: {detected_language} (forced={bool(force_language)})")

    # Log language detection for analytics
    try:
        analytics = LanguageAnalytics.get_instance()
        analytics.log_detection(
            query=question,
            detected_language=detected_language,
            force_language=force_language,
            session_id=session_id,
        )
    except Exception as e:
        logger.warning(f"Failed to log language analytics: {e}")

    allowed_labels = citation_labels_from_contexts(vector_context, graph_context, web_context)

    # Build prompt with language hint
    prompt = _build_prompt_with_language(
        question=question,
        detected_language=detected_language,
        skill_name=skill_name,
        memory_context=memory_context,
        vector_context=vector_context,
        graph_context=graph_context,
        web_context=web_context,
    )

    try:
        with bulkhead("llm"):
            model = _build_generation_model(use_reasoning=use_reasoning, question=question)
            parts: list[str] = []
            stream_failed = False
            try:
                for chunk in model.stream([("system", ANSWER_PROMPT), ("human", prompt)]):
                    content = getattr(chunk, "content", None)
                    if content:
                        text = str(content)
                        parts.append(text)
                        yield text
            except Exception as stream_error:
                logger.warning(f"Stream failed, falling back to invoke: {type(stream_error).__name__}")
                stream_failed = True

        initial = "".join(parts).strip() if parts else ""

        # If streaming failed or produced no content, fall back to invoke
        if stream_failed or not initial:
            try:
                with bulkhead("llm"):
                    result = model.invoke([("system", ANSWER_PROMPT), ("human", prompt)])
                initial = str(result.content if hasattr(result, "content") else result).strip()
                if initial:
                    if parts:
                        yield {"type": "reset", "content": initial}
                    else:
                        yield initial
            except Exception as invoke_error:
                logger.exception(f"Invoke fallback also failed: {type(invoke_error).__name__}")
                if parts:
                    yield {"type": "reset", "content": SYNTHESIS_FALLBACK_MESSAGE}
                else:
                    yield SYNTHESIS_FALLBACK_MESSAGE
                return

        if not initial:
            yield SYNTHESIS_FALLBACK_MESSAGE
            return

        final = initial
        if _self_review_enabled(enable_self_review):
            final = _refine_answer(
                question=question,
                initial_answer=initial,
                memory_context=memory_context,
                vector_context=vector_context,
                graph_context=graph_context,
                web_context=web_context,
                use_reasoning=use_reasoning,
                allowed_labels=allowed_labels,
            )
        if final != initial:
            yield {"type": "reset", "content": final}

        # Yield detected language metadata
        yield {"type": "metadata", "detected_language": detected_language}
    except Exception:
        logger.exception("Stream synthesis failed for %s", question_ref(question))
        yield SYNTHESIS_FALLBACK_MESSAGE
