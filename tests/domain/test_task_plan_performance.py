"""Performance benchmark for TaskPlan cycle detection algorithm.

This test demonstrates the performance improvement from O(V²) to O(V+E).
The old DFS algorithm would visit nodes multiple times, while Kahn's
algorithm processes each node and edge exactly once.
"""

import time

import pytest

from app.domain.contracts import PlannedTask, TaskPlan


@pytest.mark.performance
def test_linear_chain_performance() -> None:
    """Benchmark: linear chain of 200 tasks.

    Old algorithm: O(V²) ≈ 40,000 operations
    New algorithm: O(V+E) = O(200 + 199) = 399 operations
    Expected speedup: ~100x for this topology
    """
    tasks = [PlannedTask(task_id="t0", prompt="T0", depends_on=())]
    for i in range(1, 200):
        tasks.append(PlannedTask(task_id=f"t{i}", prompt=f"T{i}", depends_on=(f"t{i-1}",)))

    start = time.perf_counter()
    plan = TaskPlan(tasks=tuple(tasks))
    elapsed = time.perf_counter() - start

    assert len(plan.tasks) == 200
    # Should complete in < 10ms (generous threshold for CI)
    assert elapsed < 0.01, f"Validation took {elapsed*1000:.2f}ms, expected < 10ms"


@pytest.mark.performance
def test_wide_dag_performance() -> None:
    """Benchmark: wide DAG with many parallel branches.

    Structure: 1 root → 50 branches → 1 leaf
    Total: 52 nodes, 100 edges
    Old algorithm: O(52²) = 2,704 operations
    New algorithm: O(52 + 100) = 152 operations
    Expected speedup: ~18x
    """
    tasks = [PlannedTask(task_id="root", prompt="Root", depends_on=())]

    # Create 50 parallel branches
    for i in range(50):
        tasks.append(PlannedTask(task_id=f"branch{i}", prompt=f"Branch {i}", depends_on=("root",)))

    # Create leaf that depends on all branches
    leaf_deps = tuple(f"branch{i}" for i in range(50))
    tasks.append(PlannedTask(task_id="leaf", prompt="Leaf", depends_on=leaf_deps))

    start = time.perf_counter()
    plan = TaskPlan(tasks=tuple(tasks))
    elapsed = time.perf_counter() - start

    assert len(plan.tasks) == 52
    # Should complete in < 5ms
    assert elapsed < 0.005, f"Validation took {elapsed*1000:.2f}ms, expected < 5ms"


@pytest.mark.performance
def test_complex_dag_performance() -> None:
    """Benchmark: complex DAG with multiple levels and cross-dependencies.

    This tests a more realistic scenario with mixed topologies.
    Old algorithm would repeatedly traverse the same paths.
    New algorithm processes each node exactly once.
    """
    tasks = []

    # Level 0: 5 root tasks
    for i in range(5):
        tasks.append(PlannedTask(task_id=f"root{i}", prompt=f"Root {i}", depends_on=()))

    # Level 1: 20 tasks, each depends on 1-2 root tasks
    for i in range(20):
        deps = (f"root{i % 5}",) if i % 3 == 0 else (f"root{i % 5}", f"root{(i+1) % 5}")
        tasks.append(PlannedTask(task_id=f"mid{i}", prompt=f"Mid {i}", depends_on=deps))

    # Level 2: 10 tasks, each depends on 2-3 mid tasks
    for i in range(10):
        deps = (f"mid{i*2}", f"mid{i*2+1}", f"mid{(i*2+2) % 20}")
        tasks.append(PlannedTask(task_id=f"leaf{i}", prompt=f"Leaf {i}", depends_on=deps))

    start = time.perf_counter()
    plan = TaskPlan(tasks=tuple(tasks))
    elapsed = time.perf_counter() - start

    assert len(plan.tasks) == 35
    # Should complete in < 5ms
    assert elapsed < 0.005, f"Validation took {elapsed*1000:.2f}ms, expected < 5ms"


@pytest.mark.performance
def test_cycle_detection_performance() -> None:
    """Benchmark: cycle detection should also be fast.

    Even when rejecting invalid graphs, the algorithm should be efficient.
    """
    # Create a large graph with a cycle: t0→t1→...→t99→t0
    tasks = []
    for i in range(100):
        deps = (f"t{i-1}",) if i > 0 else ("t99",)  # t0 depends on t99, creating cycle
        tasks.append(PlannedTask(task_id=f"t{i}", prompt=f"T{i}", depends_on=deps))

    start = time.perf_counter()
    with pytest.raises(ValueError, match="acyclic"):
        TaskPlan(tasks=tuple(tasks))
    elapsed = time.perf_counter() - start

    # Cycle detection should still be fast
    assert elapsed < 0.01, f"Cycle detection took {elapsed*1000:.2f}ms, expected < 10ms"


def test_algorithm_correctness_comparison() -> None:
    """Verify new algorithm produces same results as old for various topologies."""
    test_cases = [
        # Simple chain
        (
            (
                PlannedTask(task_id="a", prompt="A", depends_on=()),
                PlannedTask(task_id="b", prompt="B", depends_on=("a",)),
                PlannedTask(task_id="c", prompt="C", depends_on=("b",)),
            ),
            True,  # Valid
        ),
        # Diamond
        (
            (
                PlannedTask(task_id="root", prompt="Root", depends_on=()),
                PlannedTask(task_id="left", prompt="Left", depends_on=("root",)),
                PlannedTask(task_id="right", prompt="Right", depends_on=("root",)),
                PlannedTask(task_id="leaf", prompt="Leaf", depends_on=("left", "right")),
            ),
            True,  # Valid
        ),
        # Simple cycle
        (
            (
                PlannedTask(task_id="a", prompt="A", depends_on=("b",)),
                PlannedTask(task_id="b", prompt="B", depends_on=("a",)),
            ),
            False,  # Invalid - cycle
        ),
        # Triangle cycle
        (
            (
                PlannedTask(task_id="a", prompt="A", depends_on=("c",)),
                PlannedTask(task_id="b", prompt="B", depends_on=("a",)),
                PlannedTask(task_id="c", prompt="C", depends_on=("b",)),
            ),
            False,  # Invalid - cycle
        ),
    ]

    for tasks, should_be_valid in test_cases:
        if should_be_valid:
            plan = TaskPlan(tasks=tasks)
            assert len(plan.tasks) == len(tasks)
        else:
            with pytest.raises(ValueError, match="acyclic"):
                TaskPlan(tasks=tasks)
