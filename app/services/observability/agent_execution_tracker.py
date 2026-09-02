import asyncio
import logging
import threading
import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import wraps
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

logger = logging.getLogger(__name__)


def utcnow():
    return datetime.now(UTC)


class AgentStep(BaseModel):
    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
    )

    step_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    agent_name: str
    start_time: datetime = Field(default_factory=utcnow)
    end_time: datetime | None = None
    duration_ms: float | None = None
    input_data: dict[str, Any] = Field(default_factory=dict)
    output_data: dict[str, Any] | None = None
    decision_rationale: str | None = None
    status: str = "running"
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class ExecutionTrace(BaseModel):
    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()},
    )

    execution_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    query: str
    user_id: str | None = None  # æ·»åŠ ç”¨æˆ·IDå­—æ®µç”¨äºŽæ•°æ®éš”ç¦»
    steps: list[AgentStep] = Field(default_factory=list)
    status: str = "running"
    start_time: datetime = Field(default_factory=utcnow)
    end_time: datetime | None = None
    total_duration_ms: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class AgentExecutionTracker:
    _instance: Optional["AgentExecutionTracker"] = None
    _lock = threading.Lock()

    def __init__(self):
        self._traces: dict[str, ExecutionTrace] = {}
        self._traces_lock = threading.RLock()  # Use RLock for reentrant locking
        self._trace_locks: dict[str, threading.RLock] = defaultdict(threading.RLock)  # Per-trace fine-grained locks
        self._ttl_hours = 1
        self._cleanup_task: asyncio.Task | None = None

    @classmethod
    def get_instance(cls) -> "AgentExecutionTracker":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def start_execution(
        self,
        query: str,
        execution_id: str | None = None,
        user_id: str | None = None,
        *,
        profile: str = "legacy",
    ) -> str:
        if execution_id is None:
            execution_id = str(uuid.uuid4())

        trace = ExecutionTrace(
            execution_id=execution_id,
            query=query,
            user_id=user_id,
            status="running",
        )

        trace.metadata["observability"] = {
            "profile": profile,
            "model_call_count": 0,
            "input_tokens": None,
            "output_tokens": None,
            "token_usage_available": False,
            "validation_trigger_reasons": [],
            "regeneration_count": 0,
        }
        with self._traces_lock:
            self._traces[execution_id] = trace

        logger.info(f"Started execution trace: {execution_id} for user: {user_id}")
        return execution_id

    def record_agent_step(
        self,
        execution_id: str,
        agent_name: str,
        input_data: dict[str, Any] | None = None,
    ) -> str:
        step = AgentStep(
            agent_name=agent_name,
            input_data=input_data or {},
            status="running",
        )

        with self._traces_lock:
            if execution_id not in self._traces:
                logger.warning(f"Execution {execution_id} not found, creating new trace")
                self._traces[execution_id] = ExecutionTrace(
                    execution_id=execution_id,
                    query="Unknown",
                )

            self._traces[execution_id].steps.append(step)

        logger.debug(f"Recorded agent step: {agent_name} in {execution_id}")
        return step.step_id

    def complete_agent_step(
        self,
        execution_id: str,
        step_id: str,
        output_data: dict[str, Any] | None = None,
        decision_rationale: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        with self._traces_lock:
            if execution_id not in self._traces:
                logger.warning(f"Execution {execution_id} not found")
                return

            trace = self._traces[execution_id]
            for step in trace.steps:
                if step.step_id == step_id:
                    step.end_time = utcnow()
                    step.duration_ms = (step.end_time - step.start_time).total_seconds() * 1000
                    step.output_data = output_data
                    step.decision_rationale = decision_rationale
                    if metadata:
                        step.metadata.update(metadata)
                    step.status = "completed"
                    logger.debug(f"Completed agent step: {step.agent_name} in {execution_id}")
                    return

            logger.warning(f"Step {step_id} not found in execution {execution_id}")

    def fail_agent_step(
        self,
        execution_id: str,
        step_id: str,
        error: str,
    ) -> None:
        with self._traces_lock:
            if execution_id not in self._traces:
                logger.warning(f"Execution {execution_id} not found")
                return

            trace = self._traces[execution_id]
            for step in trace.steps:
                if step.step_id == step_id:
                    step.end_time = utcnow()
                    step.duration_ms = (step.end_time - step.start_time).total_seconds() * 1000
                    step.status = "failed"
                    step.error = error
                    logger.debug(f"Failed agent step: {step.agent_name} in {execution_id}")
                    return

            logger.warning(f"Step {step_id} not found in execution {execution_id}")

    def complete_execution(self, execution_id: str, final_result: dict[str, Any] | None = None) -> None:
        with self._traces_lock:
            if execution_id not in self._traces:
                logger.warning(f"Execution {execution_id} not found")
                return

            trace = self._traces[execution_id]
            trace.end_time = utcnow()
            trace.total_duration_ms = (trace.end_time - trace.start_time).total_seconds() * 1000
            trace.status = "completed"
            if final_result is not None:
                trace.metadata["result"] = final_result
            logger.info(f"Completed execution trace: {execution_id}")

    def fail_execution(self, execution_id: str, error: str) -> None:
        with self._traces_lock:
            if execution_id not in self._traces:
                logger.warning(f"Execution {execution_id} not found")
                return

            trace = self._traces[execution_id]
            trace.end_time = utcnow()
            trace.total_duration_ms = (trace.end_time - trace.start_time).total_seconds() * 1000
            trace.status = "failed"
            trace.metadata["error"] = error
            logger.info(f"Failed execution trace: {execution_id}")

    def get_execution_trace(self, execution_id: str) -> ExecutionTrace | None:
        with self._traces_lock:
            return self._traces.get(execution_id)

    def get_recent_executions(self, limit: int = 20) -> list[ExecutionTrace]:
        with self._traces_lock:
            traces = list(self._traces.values())
            traces.sort(key=lambda t: t.start_time, reverse=True)
            return traces[:limit]

    def cleanup_old_traces(self) -> int:
        cutoff_time = utcnow() - timedelta(hours=self._ttl_hours)
        removed_count = 0

        with self._traces_lock:
            execution_ids_to_remove = [
                execution_id for execution_id, trace in self._traces.items() if trace.start_time < cutoff_time
            ]

            for execution_id in execution_ids_to_remove:
                del self._traces[execution_id]
                removed_count += 1

        if removed_count > 0:
            logger.info(f"Cleaned up {removed_count} old execution traces")

        return removed_count

    def clear_all_traces(self) -> None:
        with self._traces_lock:
            self._traces.clear()
            # Also clear per-trace locks to prevent memory leak
            self._trace_locks.clear()
        logger.info("Cleared all execution traces")

    def get_execution_stats(self) -> dict[str, Any]:
        """
        Get aggregated execution statistics for all agents.

        Returns:
            Dictionary with agent names as keys and their stats as values.
        """
        logger.info(f"Getting execution stats. Total traces: {len(self._traces)}")
        stats = {}

        with self._traces_lock:
            for trace_id, trace in self._traces.items():
                logger.debug(f"Processing trace {trace_id} with {len(trace.steps)} steps")
                for step in trace.steps:
                    agent_name = step.agent_name

                    if agent_name not in stats:
                        stats[agent_name] = {
                            "executions": 0,
                            "failures": 0,
                            "total_duration_ms": 0,
                            "total_tokens": 0,
                            "token_count": 0,
                            "last_execution": "",
                            "error_types": {},
                        }

                    # Count execution
                    stats[agent_name]["executions"] += 1

                    # Count failures
                    if step.status == "failed" or step.status == "error":
                        stats[agent_name]["failures"] += 1

                        # Track error types
                        error_type = step.error or "unknown"
                        # Extract error type from error message
                        if ":" in error_type:
                            error_type = error_type.split(":")[0].strip()
                        stats[agent_name]["error_types"][error_type] = (
                            stats[agent_name]["error_types"].get(error_type, 0) + 1
                        )

                    # Sum duration
                    if step.duration_ms is not None:
                        stats[agent_name]["total_duration_ms"] += step.duration_ms

                    # Sum tokens if available
                    if step.metadata and "tokens" in step.metadata:
                        stats[agent_name]["total_tokens"] += step.metadata["tokens"]
                        stats[agent_name]["token_count"] += 1

                    # Update last execution
                    if step.end_time:
                        step_time = step.end_time.isoformat()
                        if step_time > stats[agent_name]["last_execution"]:
                            stats[agent_name]["last_execution"] = step_time

        # Calculate averages
        for _agent_name, agent_stats in stats.items():
            executions = agent_stats["executions"]
            if executions > 0:
                agent_stats["avg_duration_ms"] = agent_stats["total_duration_ms"] / executions
            else:
                agent_stats["avg_duration_ms"] = 0

            token_count = agent_stats["token_count"]
            if token_count > 0:
                agent_stats["avg_tokens"] = agent_stats["total_tokens"] / token_count
            else:
                agent_stats["avg_tokens"] = 0

            # Remove internal fields
            del agent_stats["total_duration_ms"]
            del agent_stats["total_tokens"]
            del agent_stats["token_count"]

        return stats

    def get_quality_stats(self) -> dict[str, Any]:
        """
        Get comprehensive quality statistics for the dashboard.

        Returns:
            Dictionary with summary, agents, timeline, and error_distribution.
        """
        with self._traces_lock:
            agents_map: dict[str, dict[str, Any]] = {}
            timeline_map: dict[str, dict[str, int]] = {}
            error_distribution: dict[str, int] = {}

            total_executions = 0
            total_failures = 0
            total_duration_ms = 0
            execution_count = 0

            for trace in self._traces.values():
                for step in trace.steps:
                    agent_name = step.agent_name

                    # Initialize agent stats
                    if agent_name not in agents_map:
                        agents_map[agent_name] = {
                            "agent_name": agent_name,
                            "total_executions": 0,
                            "success_count": 0,
                            "failure_count": 0,
                            "total_duration_ms": 0.0,
                            "total_tokens": 0,
                            "token_count": 0,
                            "last_execution": "",
                            "error_types": {},
                        }

                    agent = agents_map[agent_name]
                    agent["total_executions"] += 1
                    total_executions += 1

                    # Track success/failure
                    if step.status == "completed":
                        agent["success_count"] += 1
                    elif step.status in ("failed", "error"):
                        agent["failure_count"] += 1
                        total_failures += 1

                        # Track error types
                        error_type = self._extract_error_type(step.error or "unknown")
                        agent["error_types"][error_type] = agent["error_types"].get(error_type, 0) + 1
                        error_distribution[error_type] = error_distribution.get(error_type, 0) + 1

                    # Track duration
                    if step.duration_ms is not None:
                        agent["total_duration_ms"] += step.duration_ms
                        total_duration_ms += step.duration_ms
                        execution_count += 1

                    # Track tokens
                    if step.metadata and "tokens" in step.metadata:
                        agent["total_tokens"] += step.metadata["tokens"]
                        agent["token_count"] += 1

                    # Update last execution
                    if step.end_time:
                        step_time = step.end_time.isoformat()
                        if step_time > agent["last_execution"]:
                            agent["last_execution"] = step_time

                    # Build timeline data (group by minute)
                    if step.end_time:
                        timestamp_key = step.end_time.strftime("%Y-%m-%dT%H:%M:00")
                        if timestamp_key not in timeline_map:
                            timeline_map[timestamp_key] = {"success": 0, "failure": 0}

                        if step.status == "completed":
                            timeline_map[timestamp_key]["success"] += 1
                        elif step.status in ("failed", "error"):
                            timeline_map[timestamp_key]["failure"] += 1

            # Calculate agent metrics
            agents = []
            active_agents = 0

            for agent in agents_map.values():
                total = agent["total_executions"]
                success = agent["success_count"]

                # Calculate rates and averages
                agent["success_rate"] = success / total if total > 0 else 0.0
                agent["avg_execution_time"] = agent["total_duration_ms"] / total / 1000.0 if total > 0 else 0.0
                agent["avg_token_usage"] = (
                    agent["total_tokens"] / agent["token_count"] if agent["token_count"] > 0 else 0.0
                )

                # Count as active if executed recently (within last hour)
                if agent["last_execution"]:
                    last_exec_time = datetime.fromisoformat(agent["last_execution"])
                    if (utcnow() - last_exec_time).total_seconds() < 3600:
                        active_agents += 1

                # Clean up temporary fields
                del agent["total_duration_ms"]
                del agent["total_tokens"]
                del agent["token_count"]

                agents.append(agent)

            # Sort agents by total executions
            agents.sort(key=lambda x: x["total_executions"], reverse=True)

            # Build timeline (sorted by timestamp)
            timeline = [
                {"timestamp": ts, "success": counts["success"], "failure": counts["failure"]}
                for ts, counts in sorted(timeline_map.items())
            ]

            # Calculate summary
            overall_success_rate = (
                (total_executions - total_failures) / total_executions if total_executions > 0 else 1.0
            )
            avg_response_time = total_duration_ms / execution_count / 1000.0 if execution_count > 0 else 0.0

            return {
                "summary": {
                    "total_agents": len(agents),
                    "total_executions": total_executions,
                    "overall_success_rate": overall_success_rate,
                    "avg_response_time": avg_response_time,
                    "active_agents": active_agents,
                },
                "agents": agents,
                "timeline": timeline,
                "error_distribution": error_distribution,
            }

    @staticmethod
    def _extract_error_type(error_message: str) -> str:
        """Extract error type from error message."""
        if not error_message:
            return "Unknown"

        # Extract the first part before colon
        if ":" in error_message:
            error_type = error_message.split(":", 1)[0].strip()
        else:
            error_type = error_message.strip()

        # Limit length
        return error_type[:50] if len(error_type) > 50 else error_type

    async def start_periodic_cleanup(self, interval_seconds: int = 300) -> None:
        """
        Start background cleanup task that periodically removes old traces.

        Args:
            interval_seconds: Cleanup interval in seconds (default: 300 = 5 minutes)
        """
        if self._cleanup_task is not None and not self._cleanup_task.done():
            logger.warning("Cleanup task already running")
            return

        self._cleanup_task = asyncio.create_task(self._cleanup_loop(interval_seconds))
        logger.info(f"Started execution tracker cleanup (interval={interval_seconds}s, ttl={self._ttl_hours}h)")

    async def _cleanup_loop(self, interval_seconds: int) -> None:
        """Background task that periodically cleans old traces."""
        while True:
            try:
                await asyncio.sleep(interval_seconds)
                removed = self.cleanup_old_traces()
                if removed > 0:
                    logger.info(f"Periodic cleanup removed {removed} old execution traces")

                # Also clean up orphaned per-trace locks
                with self._traces_lock:
                    active_ids = set(self._traces.keys())
                    lock_ids = set(self._trace_locks.keys())
                    orphaned = lock_ids - active_ids
                    for orphan_id in orphaned:
                        del self._trace_locks[orphan_id]
                    if orphaned:
                        logger.debug(f"Cleaned up {len(orphaned)} orphaned trace locks")

            except asyncio.CancelledError:
                # Re-raised, not swallowed: `break` ended this coroutine
                # *normally*, so `await task` after `task.cancel()` returned
                # instead of raising and the canceller could not tell the
                # difference between "stopped as asked" and "finished on its
                # own". `stop_periodic_cleanup` is the one that may absorb it.
                logger.info("Cleanup task cancelled")
                raise
            except Exception as e:
                logger.error(f"Error in cleanup loop: {e}", exc_info=True)

    async def stop_periodic_cleanup(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task is not None and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                # Absorbing it here is the point: this is the caller that asked
                # for the cancellation one line above, and shutdown should not
                # propagate it further.
                pass
        self._cleanup_task = None
        logger.info("Stopped execution tracker cleanup")


def track_agent_execution(agent_name: str) -> Callable:
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracker = AgentExecutionTracker.get_instance()
            execution_id = kwargs.get("execution_id")

            if not execution_id:
                logger.warning(f"No execution_id provided for {agent_name}, skipping tracking")
                return await func(*args, **kwargs)

            input_data = {k: v for k, v in kwargs.items() if k != "execution_id" and not k.startswith("_")}

            step_id = tracker.record_agent_step(
                execution_id=execution_id,
                agent_name=agent_name,
                input_data=input_data,
            )

            try:
                result = await func(*args, **kwargs)

                output_data = {}
                decision = None

                if isinstance(result, dict):
                    output_data = {k: v for k, v in result.items() if k != "execution_id"}
                    decision = result.get("decision_rationale")
                elif isinstance(result, str):
                    output_data = {"result": result}
                else:
                    output_data = {"result": str(result)}

                tracker.complete_agent_step(
                    execution_id=execution_id,
                    step_id=step_id,
                    output_data=output_data,
                    decision_rationale=decision,
                )

                return result

            except Exception as e:
                tracker.fail_agent_step(
                    execution_id=execution_id,
                    step_id=step_id,
                    error=str(e),
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracker = AgentExecutionTracker.get_instance()
            execution_id = kwargs.get("execution_id")

            if not execution_id:
                logger.warning(f"No execution_id provided for {agent_name}, skipping tracking")
                return func(*args, **kwargs)

            input_data = {k: v for k, v in kwargs.items() if k != "execution_id" and not k.startswith("_")}

            step_id = tracker.record_agent_step(
                execution_id=execution_id,
                agent_name=agent_name,
                input_data=input_data,
            )

            try:
                result = func(*args, **kwargs)

                output_data = {}
                decision = None

                if isinstance(result, dict):
                    output_data = {k: v for k, v in result.items() if k != "execution_id"}
                    decision = result.get("decision_rationale")
                elif isinstance(result, str):
                    output_data = {"result": result}
                else:
                    output_data = {"result": str(result)}

                tracker.complete_agent_step(
                    execution_id=execution_id,
                    step_id=step_id,
                    output_data=output_data,
                    decision_rationale=decision,
                )

                return result

            except Exception as e:
                tracker.fail_agent_step(
                    execution_id=execution_id,
                    step_id=step_id,
                    error=str(e),
                )
                raise

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def get_tracker() -> AgentExecutionTracker:
    """Get the singleton instance of AgentExecutionTracker."""
    return AgentExecutionTracker.get_instance()
