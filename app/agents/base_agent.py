"""
Base Agent class for all RAG agents.

Provides common functionality including:
- Error handling
- Logging
- Result formatting
- Configuration management
"""

import logging
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class AgentError(Exception):
    """Base exception for all agent errors."""
    pass


class AgentTimeoutError(AgentError):
    """Raised when agent execution times out."""
    pass


class AgentValidationError(AgentError):
    """Raised when agent input/output validation fails."""
    pass


class BaseAgent(ABC):
    """
    Base class for all RAG agents.

    Provides common functionality:
    - Configuration management
    - Error handling
    - Result formatting
    - Execution timing
    - Logging

    Subclasses must implement the `execute` method.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize base agent.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._setup_config()

    def _setup_config(self):
        """Setup agent configuration with defaults."""
        self.timeout_seconds = self.config.get("timeout_seconds", 30)
        self.enable_caching = self.config.get("enable_caching", True)
        self.log_level = self.config.get("log_level", "INFO")

    @abstractmethod
    def execute(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Execute the agent logic.

        This method must be implemented by subclasses.

        Args:
            query: User query text
            **kwargs: Additional agent-specific parameters

        Returns:
            Dictionary with execution results

        Raises:
            AgentError: If execution fails
        """
        pass

    def run(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Run the agent with error handling and timing.

        This method wraps `execute` with common functionality:
        - Input validation
        - Error handling
        - Execution timing
        - Result formatting

        Args:
            query: User query text
            **kwargs: Additional agent-specific parameters

        Returns:
            Standardized result dictionary
        """
        start_time = time.time()

        try:
            # Validate input
            self._validate_input(query, **kwargs)

            # Execute agent logic
            result = self.execute(query, **kwargs)

            # Validate output
            self._validate_output(result)

            # Calculate execution time
            execution_time_ms = (time.time() - start_time) * 1000

            # Format result
            return self._format_success_result(result, execution_time_ms)

        except AgentError as e:
            # Known agent errors
            self.logger.error(f"Agent execution failed: {e}")
            execution_time_ms = (time.time() - start_time) * 1000
            return self._format_error_result(e, execution_time_ms)

        except Exception as e:
            # Unexpected errors
            self.logger.exception(f"Unexpected error in {self.__class__.__name__}: {e}")
            execution_time_ms = (time.time() - start_time) * 1000
            return self._format_error_result(
                AgentError(f"Unexpected error: {str(e)}"),
                execution_time_ms
            )

    def _validate_input(self, query: str, **kwargs):
        """
        Validate agent input.

        Args:
            query: User query text
            **kwargs: Additional parameters

        Raises:
            AgentValidationError: If validation fails
        """
        if not query or not isinstance(query, str):
            raise AgentValidationError("Query must be a non-empty string")

        if len(query) > 10000:
            raise AgentValidationError("Query too long (max 10000 characters)")

    def _validate_output(self, result: Dict[str, Any]):
        """
        Validate agent output.

        Args:
            result: Agent execution result

        Raises:
            AgentValidationError: If validation fails
        """
        if not isinstance(result, dict):
            raise AgentValidationError(f"Result must be a dictionary, got {type(result)}")

    def _format_success_result(
        self,
        result: Dict[str, Any],
        execution_time_ms: float
    ) -> Dict[str, Any]:
        """
        Format successful execution result.

        Args:
            result: Raw agent result
            execution_time_ms: Execution time in milliseconds

        Returns:
            Standardized result dictionary
        """
        return {
            "status": "success",
            "agent_name": self.__class__.__name__,
            "execution_time_ms": round(execution_time_ms, 2),
            "timestamp": time.time(),
            **result
        }

    def _format_error_result(
        self,
        error: Exception,
        execution_time_ms: float
    ) -> Dict[str, Any]:
        """
        Format error result.

        Args:
            error: Exception that occurred
            execution_time_ms: Execution time in milliseconds

        Returns:
            Standardized error dictionary
        """
        return {
            "status": "failed",
            "agent_name": self.__class__.__name__,
            "execution_time_ms": round(execution_time_ms, 2),
            "timestamp": time.time(),
            "error": str(error),
            "error_type": type(error).__name__,
            "context": None,
            "answer": None,
        }

    def _handle_error(
        self,
        error: Exception,
        fallback_func: Optional[callable] = None,
        **fallback_kwargs
    ) -> Dict[str, Any]:
        """
        Handle errors with optional fallback.

        Args:
            error: Exception that occurred
            fallback_func: Optional fallback function to call
            **fallback_kwargs: Arguments for fallback function

        Returns:
            Error result or fallback result
        """
        self.logger.error(f"Error in {self.__class__.__name__}: {error}")

        if fallback_func:
            try:
                self.logger.info(f"Attempting fallback: {fallback_func.__name__}")
                return fallback_func(**fallback_kwargs)
            except Exception as fallback_error:
                self.logger.error(f"Fallback failed: {fallback_error}")

        return {
            "status": "failed",
            "error": str(error),
            "error_type": type(error).__name__,
        }

    def get_config_value(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value with default.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)

    def set_config_value(self, key: str, value: Any):
        """
        Set configuration value.

        Args:
            key: Configuration key
            value: Configuration value
        """
        self.config[key] = value

    def __repr__(self) -> str:
        """String representation of agent."""
        return f"{self.__class__.__name__}(config={self.config})"
