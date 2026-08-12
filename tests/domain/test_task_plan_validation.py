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
