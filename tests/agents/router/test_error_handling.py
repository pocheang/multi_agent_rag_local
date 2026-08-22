"""Test router error handling improvements."""

import pytest

from app.agents.router.service import RouterAgentService
from app.orchestration.request import OrchestrationRequest


@pytest.mark.asyncio
async def test_router_handles_missing_attributes_clearly() -> None:
    """Router should give clear error when legacy router returns invalid response."""

    class InvalidResponse:
        """Response missing required attributes."""
        pass

    def broken_decider(*args, **kwargs):
        return InvalidResponse()

    service = RouterAgentService(decider=broken_decider)
    request = OrchestrationRequest(question="test query")

    with pytest.raises(ValueError, match="Legacy router returned invalid response"):
        await service.route(request)


@pytest.mark.asyncio
async def test_router_handles_none_route_gracefully() -> None:
    """Router should use defaults when legacy router returns None values."""

    class PartialResponse:
        route = None
        confidence = None
        reason = None

    def partial_decider(*args, **kwargs):
        return PartialResponse()

    service = RouterAgentService(decider=partial_decider)
    request = OrchestrationRequest(question="test query")

    # Should not raise, should use defaults
    result = await service.route(request)

    # Defaults: route="vector", confidence=0.5, reason="legacy_router"
    assert result.effective_route == "vector"
    assert result.confidence == 0.5
    assert result.reason == "legacy_router"


@pytest.mark.asyncio
async def test_router_handles_invalid_types() -> None:
    """Router should give clear error when types cannot be converted."""

    class BadTypeResponse:
        route = object()  # Cannot convert to string
        confidence = "not a number"
        reason = "test"

    def bad_type_decider(*args, **kwargs):
        return BadTypeResponse()

    service = RouterAgentService(decider=bad_type_decider)
    request = OrchestrationRequest(question="test query")

    with pytest.raises(ValueError, match="Legacy router returned invalid response"):
        await service.route(request)


@pytest.mark.asyncio
async def test_router_preserves_valid_response() -> None:
    """Router should correctly extract valid legacy response."""

    class ValidResponse:
        route = "web"
        confidence = 0.9
        reason = "web_search_needed"

    def valid_decider(*args, **kwargs):
        return ValidResponse()

    service = RouterAgentService(decider=valid_decider)
    request = OrchestrationRequest(question="test query")

    result = await service.route(request)

    assert result.effective_route == "web"
    assert result.confidence == 0.9
    assert result.reason == "web_search_needed"
