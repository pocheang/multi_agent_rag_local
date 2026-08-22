"""Regression coverage for TaskPlan graph validity."""

import pytest
from pydantic import ValidationError

from app.domain.contracts import PlannedTask, TaskPlan


def test_task_plan_rejects_indirect_dependency_cycle() -> None:
    """Accepting a→b→a would violate the advertised DAG contract."""
    with pytest.raises(ValidationError, match="acyclic"):
        TaskPlan(
            tasks=(
                PlannedTask(task_id="retrieve", prompt="Retrieve", depends_on=("verify",)),
                PlannedTask(task_id="verify", prompt="Verify", depends_on=("retrieve",)),
            )
        )


def test_task_plan_rejects_self_cycle() -> None:
    """Self-referencing task should be rejected."""
    with pytest.raises(ValidationError, match="cannot depend on itself"):
        TaskPlan(
            tasks=(
                PlannedTask(task_id="task1", prompt="Task 1", depends_on=("task1",)),
            )
        )


def test_task_plan_rejects_longer_cycle() -> None:
    """Three-node cycle: a→b→c→a should be detected."""
    with pytest.raises(ValidationError, match="acyclic"):
        TaskPlan(
            tasks=(
                PlannedTask(task_id="a", prompt="A", depends_on=("c",)),
                PlannedTask(task_id="b", prompt="B", depends_on=("a",)),
                PlannedTask(task_id="c", prompt="C", depends_on=("b",)),
            )
        )


def test_task_plan_accepts_valid_dag() -> None:
    """Valid DAG should be accepted."""
    plan = TaskPlan(
        tasks=(
            PlannedTask(task_id="root", prompt="Root", depends_on=()),
            PlannedTask(task_id="child1", prompt="Child 1", depends_on=("root",)),
            PlannedTask(task_id="child2", prompt="Child 2", depends_on=("root",)),
            PlannedTask(task_id="leaf", prompt="Leaf", depends_on=("child1", "child2")),
        )
    )
    assert len(plan.tasks) == 4


def test_task_plan_accepts_complex_dag() -> None:
    """Complex DAG with multiple levels should be accepted."""
    plan = TaskPlan(
        tasks=(
            PlannedTask(task_id="t1", prompt="T1", depends_on=()),
            PlannedTask(task_id="t2", prompt="T2", depends_on=()),
            PlannedTask(task_id="t3", prompt="T3", depends_on=("t1",)),
            PlannedTask(task_id="t4", prompt="T4", depends_on=("t1", "t2")),
            PlannedTask(task_id="t5", prompt="T5", depends_on=("t3", "t4")),
        )
    )
    assert len(plan.tasks) == 5


def test_task_plan_performance_with_many_tasks() -> None:
    """Verify algorithm handles larger graphs efficiently (previously O(V²), now O(V+E))."""
    # Create a chain of 100 tasks: t0 → t1 → t2 → ... → t99
    tasks = [PlannedTask(task_id="t0", prompt="T0", depends_on=())]
    for i in range(1, 100):
        tasks.append(PlannedTask(task_id=f"t{i}", prompt=f"T{i}", depends_on=(f"t{i-1}",)))

    plan = TaskPlan(tasks=tuple(tasks))
    assert len(plan.tasks) == 100
