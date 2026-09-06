import asyncio
import contextlib
import logging
import threading
import uuid
from collections import defaultdict
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from functools import wraps
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.services.observability.log_safety import key_ref

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


def _blank_execution_stats() -> dict[str, Any]:
    """One agent's accumulator for `get_execution_stats`.

    `total_duration_ms`, `total_tokens` and `token_count` are working fields and
    are deleted once the averages are taken; the caller never sees them.
    """
    return {
        "executions": 0,
        "failures": 0,
        "total_duration_ms": 0,
        "total_tokens": 0,
        "token_count": 0,
        "last_execution": "",
        "error_types": {},
    }


def _execution_error_type(error: str | None) -> str:
    """The error label `get_execution_stats` groups by.

    Deliberately *not* `AgentExecutionTracker._extract_error_type`, which
    `get_quality_stats` uses: that one clamps to 50 characters and answers
    "Unknown" for an empty message, this one does neither. The two endpoints have
    therefore always been able to report different labels for the same step, and
    unifying them here would silently change what the quality dashboard groups
    by. Worth fixing deliberately, not as a side effect of a complexity refactor.
    """
    error_type = error or "unknown"
    if ":" in error_type:
        error_type = error_type.split(":")[0].strip()
    return error_type


def _accumulate_execution_step(bucket: dict[str, Any], step: "AgentStep") -> None:
    """Fold one step into one agent's `get_execution_stats` accumulator."""
    bucket["executions"] += 1

    if step.status in ("failed", "error"):
        bucket["failures"] += 1
        error_type = _execution_error_type(step.error)
        bucket["error_types"][error_type] = bucket["error_types"].get(error_type, 0) + 1

    if step.duration_ms is not None:
        bucket["total_duration_ms"] += step.duration_ms

    if step.metadata and "tokens" in step.metadata:
        bucket["total_tokens"] += step.metadata["tokens"]
        bucket["token_count"] += 1

    if step.end_time:
        step_time = step.end_time.isoformat()
        if step_time > bucket["last_execution"]:
            bucket["last_execution"] = step_time


def _finalize_execution_stats(agent_stats: dict[str, Any]) -> None:
    """Turn the accumulated totals into averages, in place, and drop the working fields."""
    executions = agent_stats["executions"]
    agent_stats["avg_duration_ms"] = agent_stats["total_duration_ms"] / executions if executions > 0 else 0

    token_count = agent_stats["token_count"]
    agent_stats["avg_tokens"] = agent_stats["total_tokens"] / token_count if token_count > 0 else 0

    del agent_stats["total_duration_ms"]
    del agent_stats["total_tokens"]
    del agent_stats["token_count"]


def _blank_agent_quality(agent_name: str) -> dict[str, Any]:
    """One agent's accumulator for `get_quality_stats`.

    The three `total_*`/`token_count` fields are working state that
    `_finalize_agent_quality` turns into averages and then deletes.
    """
    return {
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


def _blank_quality_totals() -> dict[str, Any]:
    """Run-wide counters, accumulated alongside the per-agent ones.

    `timed_steps` is not `executions`: a step with no `duration_ms` counts as an
    execution but must not dilute the average response time.
    """
    return {"executions": 0, "failures": 0, "duration_ms": 0.0, "timed_steps": 0}


def _accumulate_quality_step(
    agent: dict[str, Any],
    step: "AgentStep",
    totals: dict[str, Any],
    error_distribution: dict[str, int],
) -> None:
    """Fold one step into its agent's bucket and into the run-wide totals."""
    agent["total_executions"] += 1
    totals["executions"] += 1

    if step.status == "completed":
        agent["success_count"] += 1
    elif step.status in ("failed", "error"):
        agent["failure_count"] += 1
        totals["failures"] += 1
        error_type = _quality_error_type(step.error or "unknown")
        agent["error_types"][error_type] = agent["error_types"].get(error_type, 0) + 1
        error_distribution[error_type] = error_distribution.get(error_type, 0) + 1

    if step.duration_ms is not None:
        agent["total_duration_ms"] += step.duration_ms
        totals["duration_ms"] += step.duration_ms
        totals["timed_steps"] += 1

    if step.metadata and "tokens" in step.metadata:
        agent["total_tokens"] += step.metadata["tokens"]
        agent["token_count"] += 1

    if step.end_time:
        step_time = step.end_time.isoformat()
        if step_time > agent["last_execution"]:
            agent["last_execution"] = step_time


def _accumulate_timeline(timeline_map: dict[str, dict[str, int]], step: "AgentStep") -> None:
    """Bucket one step into the minute it finished in.

    A step with no end time is in no bucket -- it has not finished, so there is no
    minute to put it in.
    """
    if not step.end_time:
        return
    bucket = timeline_map.setdefault(step.end_time.strftime("%Y-%m-%dT%H:%M:00"), {"success": 0, "failure": 0})
    if step.status == "completed":
        bucket["success"] += 1
    elif step.status in ("failed", "error"):
        bucket["failure"] += 1


def _finalize_agent_quality(agent: dict[str, Any], now: datetime) -> bool:
    """Rates and averages in place; answers whether this agent ran in the last hour."""
    total = agent["total_executions"]
    agent["success_rate"] = agent["success_count"] / total if total > 0 else 0.0
    agent["avg_execution_time"] = agent["total_duration_ms"] / total / 1000.0 if total > 0 else 0.0
    agent["avg_token_usage"] = agent["total_tokens"] / agent["token_count"] if agent["token_count"] > 0 else 0.0

    active = False
    if agent["last_execution"]:
        active = (now - datetime.fromisoformat(agent["last_execution"])).total_seconds() < 3600

    del agent["total_duration_ms"]
    del agent["total_tokens"]
    del agent["token_count"]
    return active


def _quality_summary(total_agents: int, totals: dict[str, Any], active_agents: int) -> dict[str, Any]:
    """The dashboard header. With nothing recorded the success rate is 1.0, not 0.0."""
    executions = totals["executions"]
    timed = totals["timed_steps"]
    return {
        "total_agents": total_agents,
        "total_executions": executions,
        "overall_success_rate": (executions - totals["failures"]) / executions if executions > 0 else 1.0,
        "avg_response_time": totals["duration_ms"] / timed / 1000.0 if timed > 0 else 0.0,
        "active_agents": active_agents,
    }


def _quality_error_type(error_message: str) -> str:
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

        logger.info("execution_trace_started execution=%s user=%s", execution_id, key_ref(user_id))
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
        stats: dict[str, dict[str, Any]] = {}

        with self._traces_lock:
            for trace_id, trace in self._traces.items():
                logger.debug(f"Processing trace {trace_id} with {len(trace.steps)} steps")
                for step in trace.steps:
                    bucket = stats.setdefault(step.agent_name, _blank_execution_stats())
                    _accumulate_execution_step(bucket, step)

        # Averages are computed outside the lock: nothing here reads self._traces.
        for agent_stats in stats.values():
            _finalize_execution_stats(agent_stats)

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
            totals = _blank_quality_totals()

            for trace in self._traces.values():
                for step in trace.steps:
                    agent = agents_map.setdefault(step.agent_name, _blank_agent_quality(step.agent_name))
                    _accumulate_quality_step(agent, step, totals, error_distribution)
                    _accumulate_timeline(timeline_map, step)

            # One clock read for the whole report, so two agents cannot land on
            # opposite sides of the one-hour "active" boundary within one call.
            now = utcnow()
            active_agents = sum(_finalize_agent_quality(agent, now) for agent in agents_map.values())
            agents = sorted(agents_map.values(), key=lambda a: a["total_executions"], reverse=True)

            return {
                "summary": _quality_summary(len(agents), totals, active_agents),
                "agents": agents,
                "timeline": [
                    {"timestamp": ts, "success": counts["success"], "failure": counts["failure"]}
                    for ts, counts in sorted(timeline_map.items())
                ],
                "error_distribution": error_distribution,
            }

    @staticmethod
    def _extract_error_type(error_message: str) -> str:
        """Extract error type from error message."""
        return _quality_error_type(error_message)

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
                logger.exception(f"Error in cleanup loop: {e}")

    async def stop_periodic_cleanup(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task is not None and not self._cleanup_task.done():
            self._cleanup_task.cancel()
            # Absorbing it here is the point: this is the caller that asked for
            # the cancellation one line above, and shutdown should not propagate
            # it further. `suppress` rather than `except: pass` because the two
            # differ in what a reader has to check -- one names the exception it
            # is deliberately swallowing and covers exactly one statement, the
            # other looks like the mistake `python:S7497` exists to catch.
            with contextlib.suppress(asyncio.CancelledError):
                await self._cleanup_task
        self._cleanup_task = None
        logger.info("Stopped execution tracker cleanup")


def _tracked_input(kwargs: dict[str, Any]) -> dict[str, Any]:
    """The call's arguments, minus plumbing: the execution id and private names."""
    return {k: v for k, v in kwargs.items() if k != "execution_id" and not k.startswith("_")}


def _tracked_output(result: Any) -> tuple[dict[str, Any], str | None]:
    """A step's `output_data` and `decision_rationale`, whatever the callee returned.

    Only a mapping can carry a rationale; a bare string is recorded as itself and
    anything else through `str()`, so a step always has some output rather than
    None.
    """
    if isinstance(result, dict):
        return {k: v for k, v in result.items() if k != "execution_id"}, result.get("decision_rationale")
    if isinstance(result, str):
        return {"result": result}, None
    return {"result": str(result)}, None


def track_agent_execution(agent_name: str) -> Callable:
    """Record one agent call as a step on the caller's execution trace.

    The sync and async wrappers below were 46 duplicated lines apart from two
    `await`s until 2026-09-06 -- and cognitive complexity counts a closure into
    its enclosing function, so `track_agent_execution` carried both copies at
    once (27, `python:S3776`).
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracker = AgentExecutionTracker.get_instance()
            execution_id = kwargs.get("execution_id")
            if not execution_id:
                logger.warning(f"No execution_id provided for {agent_name}, skipping tracking")
                return await func(*args, **kwargs)

            step_id = tracker.record_agent_step(
                execution_id=execution_id,
                agent_name=agent_name,
                input_data=_tracked_input(kwargs),
            )
            # `complete_agent_step` stays inside the try on purpose: recording the
            # success is part of what can fail, and if it does the step should be
            # marked failed rather than left running.
            try:
                result = await func(*args, **kwargs)
                output_data, decision = _tracked_output(result)
                tracker.complete_agent_step(
                    execution_id=execution_id,
                    step_id=step_id,
                    output_data=output_data,
                    decision_rationale=decision,
                )
                return result
            except Exception as e:
                tracker.fail_agent_step(execution_id=execution_id, step_id=step_id, error=str(e))
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            tracker = AgentExecutionTracker.get_instance()
            execution_id = kwargs.get("execution_id")
            if not execution_id:
                logger.warning(f"No execution_id provided for {agent_name}, skipping tracking")
                return func(*args, **kwargs)

            step_id = tracker.record_agent_step(
                execution_id=execution_id,
                agent_name=agent_name,
                input_data=_tracked_input(kwargs),
            )
            try:
                result = func(*args, **kwargs)
                output_data, decision = _tracked_output(result)
                tracker.complete_agent_step(
                    execution_id=execution_id,
                    step_id=step_id,
                    output_data=output_data,
                    decision_rationale=decision,
                )
                return result
            except Exception as e:
                tracker.fail_agent_step(execution_id=execution_id, step_id=step_id, error=str(e))
                raise

        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def get_tracker() -> AgentExecutionTracker:
    """Get the singleton instance of AgentExecutionTracker."""
    return AgentExecutionTracker.get_instance()
