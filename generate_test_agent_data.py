"""
Generate test data for Agent Health Dashboard.

This script populates the AgentExecutionTracker with sample data
to demonstrate the dashboard functionality.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta, UTC
import random

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.services.agent_execution_tracker import get_tracker

def generate_test_data():
    """Generate test execution data for demonstration."""
    tracker = get_tracker()

    # Clear existing data
    tracker.clear_all_traces()

    # Agent names to simulate
    agents = [
        "router",
        "vector_rag",
        "graph_rag",
        "react",
        "synthesis",
        "enhanced_router",
        "retrieval_quality",
        "answer_validator"
    ]

    print("Generating test data for Agent Health Dashboard...")

    # Generate 50 execution traces over the last 24 hours
    now = datetime.now(UTC)
    execution_count = 0

    for i in range(50):
        # Random time in the last 24 hours
        hours_ago = random.uniform(0, 24)
        query_time = now - timedelta(hours=hours_ago)

        # Start execution
        execution_id = tracker.start_execution(
            query=f"Test query {i+1}",
            user_id="test_user"
        )

        # Simulate trace start time in the past
        if execution_id in tracker._traces:
            tracker._traces[execution_id].start_time = query_time

        # Random number of agents involved (2-5)
        num_agents = random.randint(2, 5)
        selected_agents = random.sample(agents, num_agents)

        execution_success = random.random() > 0.1  # 90% success rate

        for agent_name in selected_agents:
            # Record agent step
            step_start = query_time + timedelta(milliseconds=random.randint(10, 100))
            step_id = tracker.record_agent_step(
                execution_id=execution_id,
                agent_name=agent_name,
                input_data={"query": f"Test query {i+1}"}
            )

            # Update step start time
            if execution_id in tracker._traces:
                for step in tracker._traces[execution_id].steps:
                    if step.step_id == step_id:
                        step.start_time = step_start
                        break

            # Simulate step completion
            duration_ms = random.randint(50, 500)
            step_end = step_start + timedelta(milliseconds=duration_ms)

            if execution_success or random.random() > 0.2:  # Most steps succeed
                tracker.complete_agent_step(
                    execution_id=execution_id,
                    step_id=step_id,
                    output_data={"result": "success"},
                    metadata={"tokens": random.randint(100, 1000)}
                )

                # Update step end time
                if execution_id in tracker._traces:
                    for step in tracker._traces[execution_id].steps:
                        if step.step_id == step_id:
                            step.end_time = step_end
                            step.duration_ms = duration_ms
                            break
            else:
                # Simulate failure
                error_types = ["timeout", "invalid_input", "model_error", "connection_error"]
                tracker.fail_agent_step(
                    execution_id=execution_id,
                    step_id=step_id,
                    error=random.choice(error_types)
                )

                # Update step end time
                if execution_id in tracker._traces:
                    for step in tracker._traces[execution_id].steps:
                        if step.step_id == step_id:
                            step.end_time = step_end
                            step.duration_ms = duration_ms
                            break

        # Complete or fail execution
        total_duration = sum(
            random.randint(50, 500) for _ in selected_agents
        )
        exec_end = query_time + timedelta(milliseconds=total_duration)

        if execution_success:
            tracker.complete_execution(execution_id)
        else:
            tracker.fail_execution(execution_id, "Execution failed")

        # Update execution end time
        if execution_id in tracker._traces:
            tracker._traces[execution_id].end_time = exec_end
            tracker._traces[execution_id].total_duration_ms = total_duration

        execution_count += 1

    print(f"Generated {execution_count} test executions")

    # Display stats
    stats = tracker.get_execution_stats()
    print(f"\nGenerated stats for {len(stats)} agents:")
    for agent_name, agent_stats in stats.items():
        print(f"  - {agent_name}: {agent_stats.get('executions', 0)} executions, "
              f"{agent_stats.get('failures', 0)} failures")

    print("\nTest data generation complete!")
    print("Refresh the Agent Health dashboard to see the data.")

if __name__ == "__main__":
    generate_test_data()
