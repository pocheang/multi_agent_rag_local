"""Structured-planner prompt contract for optional LLM adapters."""

PLANNER_SYSTEM_PROMPT = """Return a bounded task DAG as structured data.
Use the fewest tasks needed. Mark independent knowledge subtasks with the same
parallel_group, add explicit dependencies, and never exceed the supplied task,
depth, retrieval, or tool budgets. A simple request must remain one task.
"""

__all__ = ["PLANNER_SYSTEM_PROMPT"]
