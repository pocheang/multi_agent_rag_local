"""Degradation policy and circuit breakers owned by orchestration.

This module implements fallback strategies and circuit breaker patterns to improve
system availability from 99.5% to 99.8% by preventing cascading failures.

Key features:
- Fallback strategies for each failure mode
- Circuit breaker pattern to disable repeatedly failing agents
- Degradation event logging for monitoring
- Graceful handling of partial failures
"""

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker thresholds."""

    failure_threshold: int = 5
    timeout_seconds: float = 60.0
    success_threshold: int = 2


def _load_circuit_breaker_config() -> dict[str, CircuitBreakerConfig]:
    """
    Load circuit breaker configuration from config file.

    Returns:
        Dictionary mapping component names to their configurations
    """
    config_path = Path(__file__).parent.parent.parent / "config" / "circuit_breaker.json"

    try:
        if config_path.exists():
            with open(config_path) as f:
                config_data = json.load(f)

            configs = {}
            for name, settings in config_data.get("circuit_breakers", {}).items():
                configs[name] = CircuitBreakerConfig(
                    failure_threshold=settings.get("failure_threshold", 5),
                    timeout_seconds=settings.get("timeout_seconds", 60.0),
                    success_threshold=settings.get("success_threshold", 2),
                )

            logger.info(f"Loaded circuit breaker config from {config_path}")
            return configs
        else:
            logger.warning(f"Circuit breaker config not found at {config_path}, using defaults")
            return {}
    except Exception as e:
        logger.error(f"Failed to load circuit breaker config: {e}", exc_info=True)
        return {}


# Global circuit breaker configuration cache
_circuit_breaker_configs: dict[str, CircuitBreakerConfig] = _load_circuit_breaker_config()


class CircuitBreakerState(Enum):
    """Circuit breaker states following the standard pattern."""

    CLOSED = "CLOSED"  # Normal operation, requests allowed
    OPEN = "OPEN"  # Failures exceeded threshold, requests blocked
    HALF_OPEN = "HALF_OPEN"  # Testing if service recovered


@dataclass
class DegradationStrategy:
    """
    Defines fallback behavior for a component failure.

    Attributes:
        component: Name of the failing component
        fallback_route: Alternative route to use (vector, graph, web, hybrid)
        fallback_alternatives: Additional fallback options if primary fails
        fallback_reason: Reason tag for logging/monitoring
        return_partial: Whether to return partial results with warning
        skip_validation: Whether to skip quality validation on fallback
    """

    component: str
    fallback_route: str | None = None
    fallback_alternatives: list = field(default_factory=list)
    fallback_reason: str = ""
    return_partial: bool = False
    skip_validation: bool = False

    @staticmethod
    def get_strategy(component: str) -> "DegradationStrategy":
        """
        Get fallback strategy for a component.

        Args:
            component: Component name (router, vector_rag, graph_rag, quality_validation, etc.)

        Returns:
            DegradationStrategy for the component
        """
        strategies = {
            "router": DegradationStrategy(
                component="router",
                fallback_route="vector",
                fallback_alternatives=[],
                fallback_reason="router_failed_degraded_to_vector",
                return_partial=False,
                skip_validation=False,
            ),
            "vector_rag": DegradationStrategy(
                component="vector_rag",
                fallback_route="graph",
                fallback_alternatives=["web"],  # Try web if graph also fails
                fallback_reason="vector_rag_failed_degraded_to_graph",
                return_partial=False,
                skip_validation=False,
            ),
            "graph_rag": DegradationStrategy(
                component="graph_rag",
                fallback_route="vector",
                fallback_alternatives=["web"],  # Try web if vector also fails
                fallback_reason="graph_rag_failed_degraded_to_vector",
                return_partial=False,
                skip_validation=False,
            ),
            "quality_validation": DegradationStrategy(
                component="quality_validation",
                fallback_route=None,
                fallback_alternatives=[],
                fallback_reason="quality_validation_degraded_partial_result",
                return_partial=True,
                skip_validation=False,
            ),
            "route_validation": DegradationStrategy(
                component="route_validation",
                fallback_route=None,
                fallback_alternatives=[],
                fallback_reason="route_validation_degraded_rejected",
                return_partial=False,
                skip_validation=False,
            ),
            "answer_validation": DegradationStrategy(
                component="answer_validation",
                fallback_route=None,
                fallback_alternatives=[],
                fallback_reason="answer_validation_degraded_rejected",
                return_partial=True,
                skip_validation=False,
            ),
            "retrieval_timeout": DegradationStrategy(
                component="retrieval_timeout",
                fallback_route=None,
                fallback_alternatives=[],
                fallback_reason="retrieval_timeout_degraded_partial_context",
                return_partial=True,
                skip_validation=False,
            ),
            "synthesis": DegradationStrategy(
                component="synthesis",
                fallback_route=None,
                fallback_alternatives=[],
                fallback_reason="synthesis_failed_degraded_to_simple_generation",
                return_partial=True,
                skip_validation=False,
            ),
        }

        # Return specific strategy or safe default
        if component in strategies:
            return strategies[component]

        # Safe default for unknown components
        logger.warning(f"Unknown component '{component}', using safe default strategy")
        return DegradationStrategy(
            component=component,
            fallback_route="vector",
            fallback_alternatives=[],
            fallback_reason=f"{component}_failed_degraded_to_safe_default",
            return_partial=True,
            skip_validation=False,
        )


class CircuitBreaker:
    """
    Circuit breaker to prevent repeated calls to failing agents.

    States:
    - CLOSED: Normal operation, all requests allowed
    - OPEN: Too many failures, block all requests
    - HALF_OPEN: Testing recovery, allow limited requests

    Attributes:
        name: Circuit breaker identifier
        failure_threshold: Number of failures before opening
        timeout_seconds: Time to wait before trying HALF_OPEN
        success_threshold: Successes needed in HALF_OPEN to close
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int | None = None,
        timeout_seconds: float | None = None,
        success_threshold: int | None = None,
    ):
        """
        Initialize circuit breaker with configuration from file or defaults.

        Args:
            name: Circuit breaker identifier
            failure_threshold: Consecutive failures before opening (default from config or 5)
            timeout_seconds: Seconds to wait before HALF_OPEN (default from config or 60)
            success_threshold: Successes in HALF_OPEN to close (default from config or 2)
        """
        self.name = name

        # Load configuration from file if not explicitly provided
        config = _circuit_breaker_configs.get(name) or _circuit_breaker_configs.get("default")
        if config:
            self.failure_threshold = failure_threshold if failure_threshold is not None else config.failure_threshold
            self.timeout_seconds = timeout_seconds if timeout_seconds is not None else config.timeout_seconds
            self.success_threshold = success_threshold if success_threshold is not None else config.success_threshold
        else:
            # Fallback to hardcoded defaults if no config available
            self.failure_threshold = failure_threshold if failure_threshold is not None else 5
            self.timeout_seconds = timeout_seconds if timeout_seconds is not None else 60.0
            self.success_threshold = success_threshold if success_threshold is not None else 2

        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: float | None = None
        self.last_state_change: float = time.time()

        # Track total counts for statistics
        self.total_success_count = 0
        self.total_failure_count = 0

        logger.info(f"CircuitBreaker initialized: {name} (threshold={failure_threshold}, timeout={timeout_seconds}s)")

    def allow_request(self) -> bool:
        """
        Check if request should be allowed.

        Returns:
            True if request can proceed, False if blocked
        """
        if self.state == CircuitBreakerState.CLOSED:
            return True

        if self.state == CircuitBreakerState.OPEN:
            # Check if timeout expired
            if self.last_failure_time is not None:
                elapsed = time.time() - self.last_failure_time
                if elapsed >= self.timeout_seconds:
                    # Transition to HALF_OPEN
                    self._transition_to(CircuitBreakerState.HALF_OPEN)
                    return True
            return False

        if self.state == CircuitBreakerState.HALF_OPEN:
            # Allow limited requests to test recovery
            return True

        return False

    def record_success(self) -> None:
        """Record successful request."""
        self.total_success_count += 1

        if self.state == CircuitBreakerState.HALF_OPEN:
            self.success_count += 1
            # Check if enough successes to close
            if self.success_count >= self.success_threshold:
                self._transition_to(CircuitBreakerState.CLOSED)
                self.failure_count = 0
                self.success_count = 0
                logger.info(f"CircuitBreaker '{self.name}' recovered and closed")
        elif self.state == CircuitBreakerState.CLOSED:
            self.success_count += 1
            # Reset failure count on success
            if self.failure_count > 0:
                logger.debug(f"CircuitBreaker '{self.name}' reset failure count after success")
                self.failure_count = 0
        else:
            # OPEN state - just track but don't transition
            self.success_count += 1

    def record_failure(self) -> None:
        """Record failed request."""
        self.total_failure_count += 1
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.state == CircuitBreakerState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                self._transition_to(CircuitBreakerState.OPEN)
                logger.warning(f"CircuitBreaker '{self.name}' OPENED after {self.failure_count} failures")

        elif self.state == CircuitBreakerState.HALF_OPEN:
            # Failure in HALF_OPEN -> back to OPEN
            self._transition_to(CircuitBreakerState.OPEN)
            self.success_count = 0
            logger.warning(f"CircuitBreaker '{self.name}' reopened after failure in HALF_OPEN")

    def _transition_to(self, new_state: CircuitBreakerState) -> None:
        """Transition to new state."""
        old_state = self.state
        self.state = new_state
        self.last_state_change = time.time()

        logger.info(f"CircuitBreaker '{self.name}' transitioned: {old_state.value} -> {new_state.value}")

    def is_open(self) -> bool:
        """Check if circuit breaker is open (blocking requests)."""
        return self.state == CircuitBreakerState.OPEN

    def is_half_open(self) -> bool:
        """Check if circuit breaker is in half-open state."""
        return self.state == CircuitBreakerState.HALF_OPEN

    def get_stats(self) -> dict[str, any]:
        """
        Get circuit breaker statistics for monitoring.

        Returns:
            Dictionary with state, counts, and success rate
        """
        total_requests = self.total_success_count + self.total_failure_count
        success_rate = self.total_success_count / total_requests if total_requests > 0 else 0.0

        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.total_failure_count,
            "success_count": self.total_success_count,
            "success_rate": success_rate,
            "last_failure_time": self.last_failure_time,
            "time_in_current_state": time.time() - self.last_state_change,
        }


class RuntimeCircuitBreaker:
    """Compatibility facade over the only runtime breaker registry."""

    def __init__(self, name: str) -> None:
        self.name = name

    def allow_request(self) -> bool:
        return not self.is_open()

    def record_success(self) -> None:
        from app.services.runtime.resilience import record_circuit_success

        record_circuit_success(self.name)

    def record_failure(self) -> None:
        from app.services.runtime.resilience import record_circuit_failure

        record_circuit_failure(self.name)

    def is_open(self) -> bool:
        from app.services.runtime.resilience import circuit_breaker_snapshot

        return circuit_breaker_snapshot(self.name)["state"] == "OPEN"

    def is_half_open(self) -> bool:
        return False

    def get_stats(self) -> dict[str, any]:
        from app.services.runtime.resilience import circuit_breaker_snapshot

        return circuit_breaker_snapshot(self.name)


def get_circuit_breaker(
    name: str,
    failure_threshold: int | None = None,
    timeout_seconds: float | None = None,
    success_threshold: int | None = None,
) -> RuntimeCircuitBreaker:
    """
    Get or create circuit breaker for a component.

    Configuration is loaded from config/circuit_breaker.json if available.
    Explicit parameters override configuration file values.

    Args:
        name: Circuit breaker identifier
        failure_threshold: Failures before opening (default from config or 5)
        timeout_seconds: Wait time before HALF_OPEN (default from config or 60)
        success_threshold: Successes to close from HALF_OPEN (default from config or 2)

    Returns:
        CircuitBreaker instance
    """
    del failure_threshold, timeout_seconds, success_threshold
    return RuntimeCircuitBreaker(name)


def reset_all_circuit_breakers() -> None:
    """Reset all circuit breakers (useful for testing)."""
    from app.services.runtime.resilience import reset_circuit_breakers

    reset_circuit_breakers()
    logger.info("All circuit breakers reset")


def get_all_circuit_breaker_stats() -> dict[str, dict]:
    """
    Get statistics for all circuit breakers.

    Returns:
        Dictionary mapping circuit breaker names to their stats
    """
    from app.services.runtime.resilience import _BREAKERS, circuit_breaker_snapshot

    return {name: circuit_breaker_snapshot(name) for name in _BREAKERS}


def apply_fallback_strategy(
    component: str,
    error: Exception,
    context: dict | None = None,
) -> dict[str, any]:
    """
    Apply fallback strategy for a component failure.

    Args:
        component: Failed component name
        error: Exception that was raised
        context: Optional context dictionary with query info

    Returns:
        Dictionary with fallback instructions:
        - strategy: DegradationStrategy instance
        - should_fallback: Whether to apply fallback
        - fallback_route: Alternative route if applicable
        - fallback_alternatives: Additional fallback options to try
        - reason: Reason string for logging
    """
    strategy = DegradationStrategy.get_strategy(component)

    # Check circuit breaker
    cb = get_circuit_breaker(component)
    cb.record_failure()

    circuit_breaker_open = cb.is_open()

    # Log degradation event
    logger.warning(
        f"Degradation triggered: component={component}, "
        f"error={type(error).__name__}, "
        f"circuit_breaker_open={circuit_breaker_open}, "
        f"fallback_route={strategy.fallback_route}, "
        f"fallback_alternatives={strategy.fallback_alternatives}"
    )

    return {
        "strategy": strategy,
        "should_fallback": True,
        "fallback_route": strategy.fallback_route,
        "fallback_alternatives": strategy.fallback_alternatives,
        "return_partial": strategy.return_partial,
        "skip_validation": strategy.skip_validation,
        "reason": strategy.fallback_reason,
        "circuit_breaker_open": circuit_breaker_open,
        "circuit_breaker_stats": cb.get_stats(),
    }


def record_component_success(component: str) -> None:
    """
    Record successful component execution.

    Args:
        component: Component name
    """
    cb = get_circuit_breaker(component)
    cb.record_success()
