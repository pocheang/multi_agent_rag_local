"""Tests the pipeline-owned assembly of typed orchestration services."""

from app.orchestration.engine import OrchestrationServices
from app.pipeline.adapters import CoreCapabilities


def test_core_capabilities_build_typed_orchestration_services() -> None:
    """Removing the typed adapter assembly would leave the engine unreachable from Pipeline."""
    services = CoreCapabilities().orchestration_services()

    assert isinstance(services, OrchestrationServices)
    assert callable(services.router)
    assert callable(services.planner)
    assert callable(services.retriever)
    assert callable(services.tool_runner)
    assert callable(services.synthesizer)
