"""
Tests for admin agent quality API endpoints.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.services.agent_execution_tracker import AgentExecutionTracker


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def admin_headers():
    """Create admin authentication headers."""
    # For testing, we'll mock admin authentication
    return {"Authorization": "Bearer test-admin-token"}


@pytest.fixture(autouse=True)
def clear_tracker():
    """Clear tracker before and after each test."""
    tracker = AgentExecutionTracker.get_instance()
    tracker.clear_all_traces()
    yield
    tracker.clear_all_traces()


def test_get_agent_quality_stats_empty(client, admin_headers, monkeypatch):
    """Test getting agent quality stats when no data exists."""
    # Mock admin authentication
    monkeypatch.setattr(
        "app.api.routes.admin_agent_quality.require_admin",
        lambda: None
    )

    response = client.get("/api/v1/admin/agent-quality/stats")
    assert response.status_code == 200

    data = response.json()
    assert "summary" in data
    assert "agents" in data
    assert "timeline" in data
    assert "error_distribution" in data

    # Should be empty
    assert data["summary"]["total_agents"] == 0
    assert data["summary"]["total_executions"] == 0
    assert len(data["agents"]) == 0


def test_get_agent_quality_stats_with_data(client, admin_headers, monkeypatch):
    """Test getting agent quality stats with execution data."""
    # Mock admin authentication
    monkeypatch.setattr(
        "app.api.routes.admin_agent_quality.require_admin",
        lambda: None
    )

    # Create some test execution data
    tracker = AgentExecutionTracker.get_instance()
    execution_id = tracker.start_execution("test query", user_id="test_user")

    # Add a successful agent step
    step_id = tracker.record_agent_step(
        execution_id=execution_id,
        agent_name="TestAgent",
        input_data={"query": "test"}
    )
    tracker.complete_agent_step(
        execution_id=execution_id,
        step_id=step_id,
        output_data={"result": "success"},
        metadata={"tokens": 1000}
    )

    # Add a failed agent step
    step_id_2 = tracker.record_agent_step(
        execution_id=execution_id,
        agent_name="TestAgent2",
        input_data={"query": "test"}
    )
    tracker.fail_agent_step(
        execution_id=execution_id,
        step_id=step_id_2,
        error="TimeoutError: Request timed out"
    )

    tracker.complete_execution(execution_id)

    # Get stats
    response = client.get("/api/v1/admin/agent-quality/stats")
    assert response.status_code == 200

    data = response.json()
    assert data["summary"]["total_agents"] == 2
    assert data["summary"]["total_executions"] == 2
    assert len(data["agents"]) == 2

    # Check agent details
    test_agent = next(a for a in data["agents"] if a["agent_name"] == "TestAgent")
    assert test_agent["total_executions"] == 1
    assert test_agent["success_count"] == 1
    assert test_agent["failure_count"] == 0
    assert test_agent["success_rate"] == 1.0

    test_agent_2 = next(a for a in data["agents"] if a["agent_name"] == "TestAgent2")
    assert test_agent_2["total_executions"] == 1
    assert test_agent_2["success_count"] == 0
    assert test_agent_2["failure_count"] == 1
    assert test_agent_2["success_rate"] == 0.0

    # Check error distribution
    assert "TimeoutError" in data["error_distribution"]
    assert data["error_distribution"]["TimeoutError"] == 1


def test_get_agent_details(client, admin_headers, monkeypatch):
    """Test getting details for a specific agent."""
    # Mock admin authentication
    monkeypatch.setattr(
        "app.api.routes.admin_agent_quality.require_admin",
        lambda: None
    )

    # Create test data
    tracker = AgentExecutionTracker.get_instance()
    execution_id = tracker.start_execution("test query")
    step_id = tracker.record_agent_step(
        execution_id=execution_id,
        agent_name="SpecificAgent",
        input_data={"test": "data"}
    )
    tracker.complete_agent_step(
        execution_id=execution_id,
        step_id=step_id,
        output_data={"result": "ok"}
    )
    tracker.complete_execution(execution_id)

    # Get specific agent details
    response = client.get("/api/v1/admin/agent-quality/agents/SpecificAgent")
    assert response.status_code == 200

    data = response.json()
    assert data["agent_name"] == "SpecificAgent"
    assert data["total_executions"] == 1
    assert data["success_rate"] == 1.0


def test_get_agent_details_not_found(client, admin_headers, monkeypatch):
    """Test getting details for non-existent agent."""
    # Mock admin authentication
    monkeypatch.setattr(
        "app.api.routes.admin_agent_quality.require_admin",
        lambda: None
    )

    response = client.get("/api/v1/admin/agent-quality/agents/NonExistentAgent")
    assert response.status_code == 404


def test_get_execution_timeline(client, admin_headers, monkeypatch):
    """Test getting execution timeline."""
    # Mock admin authentication
    monkeypatch.setattr(
        "app.api.routes.admin_agent_quality.require_admin",
        lambda: None
    )

    # Create test data
    tracker = AgentExecutionTracker.get_instance()
    execution_id = tracker.start_execution("test query")
    step_id = tracker.record_agent_step(
        execution_id=execution_id,
        agent_name="TimelineAgent"
    )
    tracker.complete_agent_step(execution_id=execution_id, step_id=step_id)
    tracker.complete_execution(execution_id)

    response = client.get("/api/v1/admin/agent-quality/timeline")
    assert response.status_code == 200

    data = response.json()
    assert "timeline" in data
    assert "summary" in data
    assert isinstance(data["timeline"], list)


def test_get_error_distribution(client, admin_headers, monkeypatch):
    """Test getting error distribution."""
    # Mock admin authentication
    monkeypatch.setattr(
        "app.api.routes.admin_agent_quality.require_admin",
        lambda: None
    )

    # Create test data with errors
    tracker = AgentExecutionTracker.get_instance()
    execution_id = tracker.start_execution("test query")

    # Add multiple error types
    for error_type in ["TimeoutError", "ValueError", "TimeoutError"]:
        step_id = tracker.record_agent_step(
            execution_id=execution_id,
            agent_name="ErrorAgent"
        )
        tracker.fail_agent_step(
            execution_id=execution_id,
            step_id=step_id,
            error=f"{error_type}: test error"
        )

    tracker.complete_execution(execution_id)

    response = client.get("/api/v1/admin/agent-quality/errors")
    assert response.status_code == 200

    data = response.json()
    assert "error_distribution" in data
    assert "total_errors" in data
    assert "top_errors" in data

    assert data["total_errors"] == 3
    assert data["error_distribution"]["TimeoutError"] == 2
    assert data["error_distribution"]["ValueError"] == 1

    # Check top errors are sorted
    assert data["top_errors"][0]["type"] == "TimeoutError"
    assert data["top_errors"][0]["count"] == 2


def test_clear_agent_stats(client, admin_headers, monkeypatch):
    """Test clearing agent statistics."""
    # Mock admin authentication
    monkeypatch.setattr(
        "app.api.routes.admin_agent_quality.require_admin",
        lambda: None
    )

    # Create test data
    tracker = AgentExecutionTracker.get_instance()
    execution_id = tracker.start_execution("test query")
    step_id = tracker.record_agent_step(execution_id=execution_id, agent_name="TestAgent")
    tracker.complete_agent_step(execution_id=execution_id, step_id=step_id)
    tracker.complete_execution(execution_id)

    # Verify data exists
    stats = tracker.get_quality_stats()
    assert stats["summary"]["total_executions"] > 0

    # Clear stats
    response = client.post("/api/v1/admin/agent-quality/clear")
    assert response.status_code == 200
    assert response.json()["status"] == "success"

    # Verify data is cleared
    stats = tracker.get_quality_stats()
    assert stats["summary"]["total_executions"] == 0
