"""Clarification Agent: gather missing fields and compose one complete query."""

from __future__ import annotations

import hashlib
import hmac

from app.agents.clarification.rules import (
    assess_completeness,
    max_rounds_for,
    missing_fields,
    question_for,
)
from app.core.config import get_settings, resolve_response_signing_secret
from app.domain.contracts import ClarificationContext
from app.domain.workflow import ClarificationResult, RouterDecision
from app.orchestration.request import OrchestrationRequest


class ClarificationAgentService:
    """Deterministic, retrieval-free multi-round clarification boundary."""

    async def clarify(
        self,
        request: OrchestrationRequest,
        route: RouterDecision | None = None,
        *,
        context: ClarificationContext | None = None,
        workflow_thread_id: str | None = None,
    ) -> ClarificationResult:
        del route
        active_context = (context or ClarificationContext()).model_copy(deep=True)
        if active_context.original_query and active_context.original_query != request.question:
            active_context = ClarificationContext(original_query=request.question)
        elif not active_context.original_query:
            active_context.original_query = request.question
        assessment = assess_completeness(request.question)
        active_context.intent = assessment.intent
        active_context.max_rounds = max_rounds_for(assessment.intent)
        thread_id = workflow_thread_id or self.workflow_thread_id(request)
        missing = missing_fields(assessment, active_context.collected_info)

        if not missing or assessment.intent == "complete":
            return ClarificationResult(
                action="continue",
                context=active_context,
                complete_query=self.compose_complete_query(request.question, active_context.collected_info),
                workflow_thread_id=thread_id,
            )

        if active_context.clarification_round >= active_context.max_rounds:
            return ClarificationResult(
                action="continue",
                context=active_context,
                complete_query=self.compose_complete_query(request.question, active_context.collected_info),
                workflow_thread_id=thread_id,
            )

        next_field = next(
            (field_name for field_name in missing if field_name not in active_context.asked_questions),
            None,
        )
        question = question_for(
            assessment.intent,
            next_field or "",
            language=_question_language(request),
        )
        if question is None:
            return ClarificationResult(
                action="continue",
                context=active_context,
                complete_query=self.compose_complete_query(request.question, active_context.collected_info),
                workflow_thread_id=thread_id,
            )
        return ClarificationResult(
            action="ask",
            question=question,
            context=active_context,
            workflow_thread_id=thread_id,
        )

    @staticmethod
    def compose_complete_query(original_query: str, collected_info: dict[str, str]) -> str:
        """Render confirmed fields without changing the user's original wording."""

        original = str(original_query or "").strip()
        confirmed = sorted(
            (str(key).strip(), str(value).strip())
            for key, value in collected_info.items()
            if str(key).strip() and str(value).strip()
        )
        if not confirmed:
            return original
        lines = [original, "", "Confirmed constraints:"]
        lines.extend(f"- {key}: {value}" for key, value in confirmed)
        return "\n".join(lines)

    @staticmethod
    def workflow_thread_id(request: OrchestrationRequest) -> str:
        actor = request.actor
        tenant_id = str((actor.tenant_id if actor else None) or (actor.user_id if actor else None) or "anonymous")
        user_id = str((actor.user_id if actor else None) or "anonymous")
        session_id = str(request.session_id or request.request_id or request.execution_id or "request-local")
        return ":".join((tenant_id, user_id, session_id))

    @staticmethod
    def issue_resume_token(workflow_thread_id: str) -> str | None:
        """Sign a correlation token when the existing response-signing key is configured."""

        _kid, secret = resolve_response_signing_secret(get_settings())
        if not secret:
            return None
        return hmac.new(secret.encode("utf-8"), workflow_thread_id.encode("utf-8"), hashlib.sha256).hexdigest()

    @classmethod
    def resume_token_is_valid(cls, workflow_thread_id: str, token: str | None) -> bool:
        expected = cls.issue_resume_token(workflow_thread_id)
        if expected is None:
            return token is None
        return bool(token) and hmac.compare_digest(expected, str(token))


def _question_language(request: OrchestrationRequest) -> str:
    """Pick the clarification language from the explicit override, then the query text.

    A Chinese-only question catalogue in a bilingual product meant English users
    were answered in Chinese, so the language is derived per request.
    """
    forced = str(getattr(request, "force_language", "") or "").strip().lower()
    if forced in {"zh", "en"}:
        return forced
    return "zh" if any("一" <= ch <= "鿿" for ch in str(request.question or "")) else "en"


__all__ = ["ClarificationAgentService"]
