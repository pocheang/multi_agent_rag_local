"""Canonical capability assembly for typed orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.agents.clarification.service import ClarificationAgentService
from app.agents.planner.service import PlannerAgentService
from app.agents.rag.service import RAGAgentService
from app.agents.router.service import RouterAgentService
from app.agents.synthesizer.service import SynthesizerAgentService
from app.agents.tool.service import ToolAgentService
from app.orchestration.engine import OrchestrationServices
from app.orchestration.finalization import FinalizationService
from app.privacy.service import PrivacyService
from app.services.security.access_scope import AccessScopeResolver


@dataclass
class CoreCapabilities:
    """Injectable canonical capabilities used by production and focused tests."""

    typed_router: RouterAgentService = field(default_factory=RouterAgentService)
    typed_clarifier: ClarificationAgentService = field(default_factory=ClarificationAgentService)
    typed_planner: PlannerAgentService = field(default_factory=PlannerAgentService)
    typed_rag: RAGAgentService = field(default_factory=RAGAgentService)
    typed_tools: ToolAgentService = field(default_factory=ToolAgentService)
    typed_synthesizer: SynthesizerAgentService = field(default_factory=SynthesizerAgentService)
    typed_finalizer: FinalizationService = field(default_factory=FinalizationService)
    privacy: PrivacyService = field(default_factory=PrivacyService)
    access_scope_resolver: AccessScopeResolver = field(default_factory=AccessScopeResolver)
    context: Any = None  # Legacy context object, type varies by implementation

    def orchestration_services(self) -> OrchestrationServices:
        """Assemble orchestration services from typed capabilities.

        The event_reporter_binder allows the orchestration engine to push
        degradation events back to RAGAgentService during retrieval failures.
        """
        return OrchestrationServices(
            router=self.typed_router.route,
            planner=self.typed_planner.plan,
            retriever=self.typed_rag.retrieve,
            tool_runner=self.typed_tools.run,
            synthesizer=self.typed_synthesizer.synthesize,
            finalizer=self.typed_finalizer.finalize,
            clarifier=self.typed_clarifier.clarify,
            privacy=self.privacy,
            access_scope_resolver=self.access_scope_resolver,
            context=self.context,
            event_reporter_binder=self.typed_rag.set_degradation_reporter,
        )


def build_orchestration_services() -> OrchestrationServices:
    """Build the sole production capability graph without compatibility wrappers."""
    return CoreCapabilities().orchestration_services()


__all__ = ["CoreCapabilities", "build_orchestration_services"]
