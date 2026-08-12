"""Canonical capability assembly for typed orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.agents.planner.service import PlannerAgentService
from app.agents.rag.service import RAGAgentService
from app.agents.router.service import RouterAgentService
from app.agents.synthesizer.service import SynthesizerAgentService
from app.agents.tool.service import ToolAgentService
from app.orchestration.engine import OrchestrationServices
from app.orchestration.finalization import FinalizationService


@dataclass
class CoreCapabilities:
    """Injectable canonical capabilities used by production and focused tests."""

    typed_router: Any = field(default_factory=RouterAgentService)
    typed_planner: Any = field(default_factory=PlannerAgentService)
    typed_rag: Any = field(default_factory=RAGAgentService)
    typed_tools: Any = field(default_factory=ToolAgentService)
    typed_synthesizer: Any = field(default_factory=SynthesizerAgentService)
    typed_finalizer: Any = field(default_factory=FinalizationService)
    context: Any = None

    def orchestration_services(self) -> OrchestrationServices:
        reporter_binder = getattr(self.typed_rag, "set_degradation_reporter", None)
        return OrchestrationServices(
            router=self.typed_router.route,
            planner=self.typed_planner.plan,
            retriever=self.typed_rag.retrieve,
            tool_runner=self.typed_tools.run,
            synthesizer=self.typed_synthesizer.synthesize,
            finalizer=self.typed_finalizer.finalize,
            context=self.context,
            event_reporter_binder=reporter_binder if callable(reporter_binder) else None,
        )


def build_orchestration_services() -> OrchestrationServices:
    """Build the sole production capability graph without compatibility wrappers."""
    return CoreCapabilities().orchestration_services()


__all__ = ["CoreCapabilities", "build_orchestration_services"]
